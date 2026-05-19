import 'dart:io';

import 'package:dio/dio.dart';

import '../models/awaz_log_entry.dart';
import '../models/outcome.dart';

class AwazApiService {
  final Dio _dio;

  AwazApiService({required String baseUrl})
      : _dio = Dio(BaseOptions(baseUrl: baseUrl, connectTimeout: const Duration(seconds: 20), receiveTimeout: const Duration(seconds: 30)));

  Future<void> processText(String text) async {
    await _dio.post('/api/process/text', data: {'text': text});
  }

  Future<void> processVoice(File audioFile) async {
    final formData = FormData.fromMap({
      'audio': await MultipartFile.fromFile(audioFile.path, filename: 'recording.wav'),
    });
    await _dio.post('/api/process/voice', data: formData);
  }

  Future<List<AwazLogEntry>> fetchLogs() async {
    final resp = await _dio.get('/api/logs');
    final data = resp.data;
    if (data is! List) return [];
    return data.whereType<Map<String, dynamic>>().map(AwazLogEntry.fromJson).toList();
  }

  Future<Outcome?> fetchOutcome() async {
    try {
      final resp = await _dio.get('/api/outcome');
      if (resp.data is Map<String, dynamic>) {
        return Outcome.fromJson(resp.data as Map<String, dynamic>);
      }
      return null;
    } catch (_) {
      return null;
    }
  }
}
