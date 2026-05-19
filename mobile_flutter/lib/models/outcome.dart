class Outcome {
  final String verdict;
  final String summaryEn;
  final String summaryUr;
  final int tokenEstimate;
  final String allocationBefore;
  final String allocationAfter;
  final double riskBefore;
  final double riskAfter;
  final int latencyMs;

  Outcome({
    required this.verdict,
    required this.summaryEn,
    required this.summaryUr,
    required this.tokenEstimate,
    required this.allocationBefore,
    required this.allocationAfter,
    required this.riskBefore,
    required this.riskAfter,
    required this.latencyMs,
  });

  factory Outcome.fromJson(Map<String, dynamic> json) {
    final metrics = (json['metrics_changed'] as Map<String, dynamic>? ?? {});
    final allocation = (metrics['portfolio_allocation'] as Map<String, dynamic>? ?? {});
    final risk = (metrics['risk_score'] as Map<String, dynamic>? ?? {});
    final latency = (json['latency_summary'] as Map<String, dynamic>? ?? {});

    final totalLatency = ((latency['ingestion_ms'] as num?)?.toDouble() ?? 0) +
        ((latency['execution_ms'] as num?)?.toDouble() ?? 0) +
        ((latency['monitor_ms'] as num?)?.toDouble() ?? 0);

    return Outcome(
      verdict: (json['verdict'] ?? '').toString(),
      summaryEn: (json['summary_en'] ?? '').toString(),
      summaryUr: (json['summary_ur'] ?? '').toString(),
      tokenEstimate: (json['token_estimate'] as num?)?.toInt() ?? 0,
      allocationBefore: (allocation['before'] ?? '0%').toString(),
      allocationAfter: (allocation['after'] ?? '0%').toString(),
      riskBefore: (risk['before'] as num?)?.toDouble() ?? 0,
      riskAfter: (risk['after'] as num?)?.toDouble() ?? 0,
      latencyMs: totalLatency.round(),
    );
  }
}
