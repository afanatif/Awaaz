class AwazLogEntry {
  final String timestamp;
  final String agentName;
  final String eventType;
  final dynamic inputSummary;
  final dynamic outputSummary;
  final double? durationMs;
  final String? error;
  final String? verdict;
  final double? contradictionScore;
  final Map<String, dynamic> raw;

  AwazLogEntry({
    required this.timestamp,
    required this.agentName,
    required this.eventType,
    required this.raw,
    this.inputSummary,
    this.outputSummary,
    this.durationMs,
    this.error,
    this.verdict,
    this.contradictionScore,
  });

  factory AwazLogEntry.fromJson(Map<String, dynamic> json) {
    return AwazLogEntry(
      timestamp: (json['timestamp'] ?? '').toString(),
      agentName: (json['agent_name'] ?? 'system').toString(),
      eventType: (json['event_type'] ?? '').toString(),
      inputSummary: json['input_summary'],
      outputSummary: json['output_summary'],
      durationMs: (json['duration_ms'] as num?)?.toDouble(),
      error: json['error']?.toString(),
      verdict: json['verdict']?.toString(),
      contradictionScore: (json['contradiction_score'] as num?)?.toDouble(),
      raw: json,
    );
  }

  String get summary {
    final candidate = outputSummary ?? inputSummary;
    return candidate == null ? '' : candidate.toString();
  }

  bool get isError => error != null || eventType.toLowerCase().contains('fail');

  String get timeOnly {
    if (timestamp.length < 19) return timestamp;
    return timestamp.substring(11, 19);
  }
}
