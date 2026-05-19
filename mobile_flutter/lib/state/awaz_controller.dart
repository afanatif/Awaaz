import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../models/awaz_log_entry.dart';
import '../models/outcome.dart';
import '../models/source_intel_item.dart';
import '../services/awaz_api_service.dart';
import '../services/awaz_socket_service.dart';

class AwazController extends ChangeNotifier {
  final AwazApiService api;
  final AwazSocketService socket;

  final List<AwazLogEntry> logs = [];
  final Map<String, String> sourceStatus = {};
  final Map<String, String> actionStatus = {};

  List<SourceIntelItem> sourceIntel = [];
  Outcome? outcome;

  String banner = 'Idle — waiting for input.';
  String systemStatus = 'Ready';
  String currentAgent = '';
  String transcription = '';
  String verdict = '';
  String analystNarrative = '';
  double contradictionScore = 0.5;

  StreamSubscription<AwazLogEntry>? _sub;

  static const Map<String, String> _sourceLabelMap = {
    'NewsAPI': 'News',
    'Yahoo Finance': 'Market',
    'Reddit': 'Reddit',
    'SBP + Exchange Rate': 'Regulatory/Macro',
    'SBP Website': 'Regulatory/Macro',
    'Exchange Rate API': 'Regulatory/Macro',
    'Business Recorder': 'Business Recorder',
    'PSX Data Portal': 'PSX',
  };

  AwazController({required this.api, required this.socket});

  Future<void> initialize() async {
    socket.connect();
    _sub = socket.stream.listen(_onLogEntry);
    await hydrateFromHistory();
  }

  Future<void> hydrateFromHistory() async {
    final all = await api.fetchLogs();
    final lastStartup = all.lastIndexWhere((e) => e.eventType == 'startup');
    final scoped = lastStartup >= 0 ? all.sublist(lastStartup) : all;

    logs.clear();
    sourceStatus.clear();
    actionStatus.clear();
    sourceIntel = [];
    outcome = null;
    transcription = '';
    verdict = '';
    analystNarrative = '';
    contradictionScore = 0.5;

    for (final entry in scoped) {
      _processLog(entry, fromHistory: true);
    }
    notifyListeners();
  }

  Future<void> processText(String text) async {
    _resetRunState();
    await api.processText(text);
  }

  Future<void> processVoice(File file) async {
    _resetRunState();
    await api.processVoice(file);
  }

  void _resetRunState() {
    logs.clear();
    sourceStatus.clear();
    actionStatus.clear();
    sourceIntel = [];
    outcome = null;
    transcription = '';
    verdict = '';
    analystNarrative = '';
    contradictionScore = 0.5;
    systemStatus = 'Processing...';
    banner = 'Pipeline running… waiting for first agent output.';
    currentAgent = '';
    notifyListeners();
  }

  void _onLogEntry(AwazLogEntry entry) {
    _processLog(entry, fromHistory: false);
    notifyListeners();
  }

  void _processLog(AwazLogEntry entry, {required bool fromHistory}) {
    logs.add(entry);

    if (entry.agentName != 'system') {
      currentAgent = entry.agentName;
      final cap = '${entry.agentName[0].toUpperCase()}${entry.agentName.substring(1)}';
      banner = 'This agent is running: $cap';
      systemStatus = 'Processing...';
    }

    if (entry.eventType == 'language_translation' || entry.eventType == 'whisper_transcription_completed') {
      transcription = entry.summary;
    }

    if (entry.eventType == 'source_fetch_completed' || entry.eventType == 'source_fetch_failed') {
      final raw = (entry.inputSummary ?? '').toString();
      String label = _sourceLabelMap[raw] ?? raw;
      if (raw.contains('SBP') || raw.contains('Exchange Rate')) {
        label = 'Regulatory/Macro';
      }
      sourceStatus[label] = entry.eventType == 'source_fetch_completed' ? 'ok' : 'fallback';
    }

    if (entry.eventType == 'analysis_completed') {
      verdict = (entry.verdict ?? '').toUpperCase();
      contradictionScore = entry.contradictionScore ?? 0.5;
      sourceIntel = _deriveSourceIntel(entry);
      analystNarrative = _buildAnalystNarrative(entry);
    }

    if (entry.eventType == 'action_generated') {
      final actionName = (entry.raw['action_name'] ?? entry.summary).toString();
      actionStatus[actionName] = 'Pending';
    }

    if (entry.eventType == 'execution_completed' || entry.eventType == 'execution_failed') {
      final actionName = _extractActionName((entry.inputSummary ?? '').toString());
      if (actionName.isNotEmpty) {
        actionStatus[actionName] = entry.eventType == 'execution_completed' ? 'Completed' : 'Failed';
      }
    }

    if (entry.eventType == 'pipeline_completed') {
      banner = '🎉 Pipeline complete! Outcome saved and dashboard updated.';
      systemStatus = 'Complete';
      _fetchOutcome();
    }
  }

  String _extractActionName(String input) {
    final bracket = RegExp(r'\[\d+\]\s*(?:[^:]+:\s*)?(.+)').firstMatch(input);
    if (bracket != null && bracket.groupCount >= 1) {
      return (bracket.group(1) ?? '').trim();
    }
    return input.trim();
  }

  List<SourceIntelItem> _deriveSourceIntel(AwazLogEntry analysisEntry) {
    final structured = _deriveSourceIntelFromAnalysisEntry(analysisEntry);
    if (structured.isNotEmpty) {
      return structured;
    }
    return _deriveSourceIntelFromLogs();
  }

  List<SourceIntelItem> _deriveSourceIntelFromAnalysisEntry(AwazLogEntry analysisEntry) {
    final Map<String, dynamic>? sourceScores = analysisEntry.raw['source_scores'] is Map<String, dynamic>
        ? analysisEntry.raw['source_scores'] as Map<String, dynamic>
        : null;
    final Map<String, dynamic>? sourceEvidence = analysisEntry.raw['source_evidence'] is Map<String, dynamic>
        ? analysisEntry.raw['source_evidence'] as Map<String, dynamic>
        : null;
    final Map<String, dynamic>? sourceReasoning = analysisEntry.raw['source_reasoning'] is Map<String, dynamic>
        ? analysisEntry.raw['source_reasoning'] as Map<String, dynamic>
        : null;

    if (sourceScores == null || sourceScores.isEmpty) return [];

    const order = [
      'news',
      'market',
      'reddit',
      'regulatory',
      'business_recorder',
      'psx',
      'dawn_business',
      'profit_pakistan',
    ];

    final items = <SourceIntelItem>[];
    for (final key in order) {
      final dynamic rawScore = sourceScores[key];
      if (rawScore == null) continue;
      final score = (rawScore as num).toDouble();
      items.add(SourceIntelItem(
        sourceKey: key,
        sourceLabel: _prettySource(key),
        stance: _stance(score),
        evidence: (sourceEvidence?[key] ?? 'No evidence text available.').toString(),
        reasoning: (sourceReasoning?[key] ?? 'No analyst reasoning provided for this source.').toString(),
        score: score,
      ));
    }

    return items;
  }

  List<SourceIntelItem> _deriveSourceIntelFromLogs() {
    final Map<String, SourceIntelItem> map = {};

    for (final e in logs.where((x) => x.agentName == 'analyst')) {
      if (e.eventType == 'contradiction_detected' || e.eventType == 'no_contradiction_found') {
        final input = (e.inputSummary ?? '').toString();
        final source = input.split(':').first.trim();
        final score = _extractScore(input) ?? 0.5;
        map[source] = SourceIntelItem(
          sourceKey: source,
          sourceLabel: _prettySource(source),
          stance: _stance(score),
          evidence: e.summary.isEmpty ? 'No detailed source summary available for this run.' : e.summary,
          reasoning: 'Reasoning extracted from analyst event stream.',
          score: score,
        );
      }

      if (e.eventType == 'reddit_sentiment_analyzed') {
        final out = e.summary;
        final score = _extractContraFromSummary(out) ?? 0.5;
        map['reddit'] = SourceIntelItem(
          sourceKey: 'reddit',
          sourceLabel: 'Reddit',
          stance: _stance(score),
          evidence: out,
          reasoning: 'Reddit sentiment contributed to contradiction scoring.',
          score: score,
        );
      }
    }

    const order = [
      'news',
      'market',
      'reddit',
      'regulatory',
      'business_recorder',
      'psx',
      'dawn_business',
      'profit_pakistan',
    ];
    return order.where(map.containsKey).map((k) => map[k]!).toList();
  }

  String _buildAnalystNarrative(AwazLogEntry analysisEntry) {
    final verdictText = (analysisEntry.verdict ?? verdict).toUpperCase();
    final score = analysisEntry.contradictionScore ?? contradictionScore;
    final sourceReasoning = analysisEntry.raw['source_reasoning'];

    if (sourceReasoning is Map<String, dynamic> && sourceReasoning.isNotEmpty) {
      final top = sourceReasoning.entries
          .where((e) => e.value != null && e.value.toString().trim().isNotEmpty)
          .take(3)
          .map((e) => '${_prettySource(e.key)}: ${e.value}')
          .join('\n\n');

      if (top.isNotEmpty) {
        return 'Verdict: $verdictText (contradiction score ${score.toStringAsFixed(2)}).\n\n'
            'Analyst synthesis:\n$top';
      }
    }

    return 'Verdict: $verdictText (contradiction score ${score.toStringAsFixed(2)}). '
        'Detailed source reasoning was not available in this run.';
  }

  double? _extractScore(String input) {
    final match = RegExp(r'score\s*=\s*([0-9]*\.?[0-9]+)', caseSensitive: false).firstMatch(input);
    if (match == null) return null;
    return double.tryParse(match.group(1)!);
  }

  double? _extractContraFromSummary(String summary) {
    final match = RegExp(r'contra\s*=\s*([0-9]*\.?[0-9]+)', caseSensitive: false).firstMatch(summary);
    if (match == null) return null;
    return double.tryParse(match.group(1)!);
  }

  String _prettySource(String key) {
    switch (key) {
      case 'news':
        return 'News';
      case 'market':
        return 'Market';
      case 'reddit':
        return 'Reddit';
      case 'regulatory':
        return 'Regulatory/Macro';
      case 'business_recorder':
        return 'Business Recorder';
      case 'psx':
        return 'PSX';
      case 'dawn_business':
        return 'Dawn Business';
      case 'profit_pakistan':
        return 'Profit Pakistan';
      default:
        return key;
    }
  }

  String _stance(double score) {
    if (score >= 0.6) return 'Contradicts';
    if (score <= 0.4) return 'Supports';
    return 'Unclear';
  }

  Future<void> _fetchOutcome() async {
    outcome = await api.fetchOutcome();
    notifyListeners();
  }

  @override
  void dispose() {
    _sub?.cancel();
    socket.dispose();
    super.dispose();
  }
}
