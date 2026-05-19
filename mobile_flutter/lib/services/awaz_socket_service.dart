import 'dart:async';

import 'package:socket_io_client/socket_io_client.dart' as io;

import '../models/awaz_log_entry.dart';

class AwazSocketService {
  final String baseUrl;
  io.Socket? _socket;
  final StreamController<AwazLogEntry> _controller = StreamController.broadcast();

  AwazSocketService({required this.baseUrl});

  Stream<AwazLogEntry> get stream => _controller.stream;

  void connect() {
    _socket?.dispose();
    _socket = io.io(
      baseUrl,
      io.OptionBuilder().setTransports(['websocket', 'polling']).disableAutoConnect().build(),
    );

    _socket!.on('log_entry', (data) {
      if (data is Map) {
        final map = Map<String, dynamic>.from(data as Map);
        _controller.add(AwazLogEntry.fromJson(map));
      }
    });

    _socket!.connect();
  }

  void disconnect() {
    _socket?.disconnect();
    _socket?.dispose();
    _socket = null;
  }

  void dispose() {
    disconnect();
    _controller.close();
  }
}
