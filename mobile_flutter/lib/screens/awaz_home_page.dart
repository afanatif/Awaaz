import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../models/awaz_log_entry.dart';
import '../models/source_intel_item.dart';
import '../services/awaz_api_service.dart';
import '../services/awaz_socket_service.dart';
import '../state/awaz_controller.dart';

class AwazHomePage extends StatefulWidget {
  const AwazHomePage({super.key});

  @override
  State<AwazHomePage> createState() => _AwazHomePageState();
}

class _AwazHomePageState extends State<AwazHomePage> {
  static const String backendBaseUrl = String.fromEnvironment(
    'AWAZ_BASE_URL',
    defaultValue: 'http://192.168.100.5:5000',
  );

  late final AwazController controller;
  final TextEditingController textController = TextEditingController();
  final AudioRecorder recorder = AudioRecorder();

  bool recording = false;
  String? recordingPath;

  @override
  void initState() {
    super.initState();
    controller = AwazController(
      api: AwazApiService(baseUrl: backendBaseUrl),
      socket: AwazSocketService(baseUrl: backendBaseUrl),
    )..initialize();
    controller.addListener(_onControllerChanged);
  }

  void _onControllerChanged() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    controller.removeListener(_onControllerChanged);
    controller.dispose();
    textController.dispose();
    recorder.dispose();
    super.dispose();
  }

  Future<void> _sendText() async {
    final text = textController.text.trim();
    if (text.isEmpty) return;
    await controller.processText(text);
    textController.clear();
  }

  Future<void> _startRecording() async {
    final allowed = await recorder.hasPermission();
    if (!allowed) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Microphone permission is required.')),
      );
      return;
    }

    final dir = await getTemporaryDirectory();
    recordingPath = '${dir.path}/awaz_recording.wav';
    await recorder.start(const RecordConfig(encoder: AudioEncoder.wav), path: recordingPath!);
    setState(() => recording = true);
  }

  Future<void> _stopRecordingAndSend() async {
    if (!recording) return;
    await recorder.stop();
    setState(() => recording = false);

    if (recordingPath == null) return;
    final file = File(recordingPath!);
    if (await file.exists()) {
      await controller.processVoice(file);
    }
  }

  Color _agentColor(String agent) {
    switch (agent) {
      case 'ingestion':
        return const Color(0xFFFF8A3D);
      case 'analyst':
        return const Color(0xFF3DDDB3);
      case 'strategist':
        return const Color(0xFF4DA2FF);
      case 'executor':
        return const Color(0xFF63D95A);
      case 'monitor':
        return const Color(0xFFFFD84D);
      default:
        return const Color(0xFF9FB4D4);
    }
  }

  @override
  Widget build(BuildContext context) {
    final sourceStatus = controller.sourceStatus.entries.toList();
    final logs = controller.logs.reversed.take(120).toList();
    final processing = controller.systemStatus == 'Processing...';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Awaz Intelligence'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 16),
            child: Center(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(999),
                  color: processing ? const Color(0x334DA2FF) : const Color(0x3340D991),
                ),
                child: Text(controller.systemStatus),
              ),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: controller.hydrateFromHistory,
          child: ListView(
            padding: const EdgeInsets.all(12),
            children: [
              _heroCard(),
              const SizedBox(height: 12),
              _bannerCard(),
              const SizedBox(height: 12),
              _inputCard(),
              const SizedBox(height: 12),
              _agentRow(),
              const SizedBox(height: 12),
              if (controller.transcription.isNotEmpty) _transcriptionCard(),
              if (sourceStatus.isNotEmpty) _sourcesChipCard(sourceStatus),
              if (controller.analystNarrative.isNotEmpty) _analystNarrativeCard(),
              if (controller.sourceIntel.isNotEmpty) _sourceIntelCard(controller.sourceIntel),
              if (controller.verdict.isNotEmpty) _verdictCard(),
              if (controller.actionStatus.isNotEmpty) _actionsCard(),
              if (controller.outcome != null) _outcomeCard(),
              const SizedBox(height: 12),
              _traceCard(logs),
            ],
          ),
        ),
      ),
    );
  }

  Widget _analystNarrativeCard() {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('Analyst Narrative'),
            const SizedBox(height: 8),
            Text(
              controller.analystNarrative,
              style: const TextStyle(height: 1.35),
            ),
          ],
        ),
      ),
    );
  }

  Widget _heroCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: const LinearGradient(
          colors: [Color(0xFF0F1A2B), Color(0xFF132743)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        border: Border.all(color: const Color(0xFF21324E)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'Explainable Multi-Agent Intelligence',
            style: TextStyle(fontWeight: FontWeight.w800, fontSize: 16),
          ),
          const SizedBox(height: 6),
          const Text(
            'One claim in. Contradiction verdict, source reasoning, and action chain out.',
            style: TextStyle(color: Colors.white70),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _metricPill('Agents', '5'),
              _metricPill('Sources', controller.sourceStatus.isEmpty ? '8' : '${controller.sourceStatus.length}'),
              _metricPill('Mode', controller.systemStatus),
            ],
          )
        ],
      ),
    );
  }

  Widget _metricPill(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        color: const Color(0xFF0B1220),
        border: Border.all(color: const Color(0xFF29374D)),
      ),
      child: Text('$label: $value', style: const TextStyle(fontSize: 12, color: Colors.white70)),
    );
  }

  Widget _bannerCard() {
    final complete = controller.systemStatus == 'Complete';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        color: complete ? const Color(0x3340D991) : const Color(0x334DA2FF),
        border: Border.all(color: complete ? const Color(0xFF63D95A) : const Color(0xFF4DA2FF)),
      ),
      child: Text(controller.banner, style: const TextStyle(fontWeight: FontWeight.w600)),
    );
  }

  Widget _inputCard() {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('Start Investigation'),
            const SizedBox(height: 10),
            TextField(
              controller: textController,
              decoration: const InputDecoration(
                hintText: 'Type a business claim or decision hypothesis...',
                border: OutlineInputBorder(),
              ),
              onSubmitted: (_) => _sendText(),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                Expanded(
                  child: FilledButton(
                    onPressed: _sendText,
                    child: const Text('Send'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: GestureDetector(
                    onLongPressStart: (_) => _startRecording(),
                    onLongPressEnd: (_) => _stopRecordingAndSend(),
                    child: Container(
                      height: 48,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(10),
                        color: recording ? const Color(0xFFEF4444) : const Color(0xFF1F2937),
                      ),
                      alignment: Alignment.center,
                      child: Text(recording ? 'Recording... release' : 'Hold to Speak'),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _agentRow() {
    const agents = ['ingestion', 'analyst', 'strategist', 'executor', 'monitor'];
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Wrap(
          spacing: 8,
          runSpacing: 8,
          children: agents.map((a) {
            final active = controller.currentAgent == a;
            return Container(
              width: 100,
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: active ? _agentColor(a) : const Color(0xFF334155)),
                color: active ? _agentColor(a).withValues(alpha: 0.18) : const Color(0xFF111827),
              ),
              child: Column(
                children: [
                  Text(a.toUpperCase(), style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Text(active ? 'Running' : 'Idle', style: const TextStyle(fontSize: 11, color: Colors.white70)),
                ],
              ),
            );
          }).toList(),
        ),
      ),
    );
  }

  Widget _transcriptionCard() {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('Transcription'),
            const SizedBox(height: 6),
            Text('"${controller.transcription}"'),
          ],
        ),
      ),
    );
  }

  Widget _sourcesChipCard(List<MapEntry<String, String>> entries) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('Source Coverage'),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: entries
                  .map((e) => Chip(
                        label: Text('${e.key}: ${e.value}'),
                        backgroundColor: e.value == 'ok' ? const Color(0x3340D991) : const Color(0x33EF4444),
                      ))
                  .toList(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sourceIntelCard(List<SourceIntelItem> items) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('Why This Verdict'),
            const SizedBox(height: 8),
            ...items.map((item) {
              final color = item.stance == 'Contradicts'
                  ? const Color(0xFFFF5D7E)
                  : item.stance == 'Supports'
                      ? const Color(0xFF63D95A)
                      : const Color(0xFFFFD84D);
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: const Color(0xFF334155)),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(child: Text(item.sourceLabel, style: const TextStyle(fontWeight: FontWeight.w700))),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(color: color.withValues(alpha: 0.2), borderRadius: BorderRadius.circular(999)),
                          child: Text(item.stance, style: TextStyle(color: color, fontSize: 11)),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      item.reasoning,
                      style: const TextStyle(height: 1.35),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: const Color(0xFF0F172A),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: const Color(0xFF273449)),
                      ),
                      child: Text(
                        'Evidence: ${item.evidence}',
                        style: const TextStyle(color: Colors.white70, height: 1.3),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Contradiction score: ${item.score.toStringAsFixed(2)}',
                      style: const TextStyle(color: Colors.white70),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }

  Widget _verdictCard() {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('Verdict'),
            const SizedBox(height: 8),
            Text(controller.verdict, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            LinearProgressIndicator(
              value: controller.contradictionScore.clamp(0, 1),
              minHeight: 10,
              color: controller.contradictionScore >= 0.6
                  ? const Color(0xFFFF5D7E)
                  : controller.contradictionScore <= 0.4
                      ? const Color(0xFF63D95A)
                      : const Color(0xFFFFD84D),
              backgroundColor: const Color(0xFF1F2937),
            ),
          ],
        ),
      ),
    );
  }

  Widget _actionsCard() {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('Action Chain'),
            const SizedBox(height: 8),
            ...controller.actionStatus.entries.map((e) => ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text(e.key),
                  trailing: Text(
                    e.value,
                    style: TextStyle(
                      color: e.value == 'Completed' ? const Color(0xFF63D95A) : const Color(0xFFFF5D7E),
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                )),
          ],
        ),
      ),
    );
  }

  Widget _outcomeCard() {
    final o = controller.outcome!;
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('Decision Dashboard'),
            const SizedBox(height: 8),
            Text('Allocation: ${o.allocationBefore} → ${o.allocationAfter}'),
            Text('Risk: ${o.riskBefore} → ${o.riskAfter}'),
            Text('Tokens Used: ${o.tokenEstimate}'),
            Text('Total Latency: ${o.latencyMs}ms'),
            const SizedBox(height: 8),
            Text(o.summaryEn),
            const SizedBox(height: 8),
            Text(o.summaryUr, textDirection: TextDirection.rtl),
          ],
        ),
      ),
    );
  }

  Widget _traceCard(List<AwazLogEntry> entries) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _sectionTitle('Audit Trail'),
            const SizedBox(height: 8),
            SizedBox(
              height: 320,
              child: ListView.builder(
                itemCount: entries.length,
                itemBuilder: (context, i) {
                  final e = entries[i];
                  final col = e.isError ? const Color(0xFFFF5D7E) : _agentColor(e.agentName);
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text(
                      '[${e.timeOnly}] [${e.agentName.toUpperCase()}] ${e.eventType} ${e.summary}',
                      style: TextStyle(fontSize: 12, color: col),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sectionTitle(String text) {
    return Text(
      text,
      style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
    );
  }
}
