import 'package:flutter/material.dart';

import 'screens/awaz_home_page.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const AwazMobileApp());
}

class AwazMobileApp extends StatelessWidget {
  const AwazMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Awaz Mobile',
      theme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF4DA2FF),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xFF090D14),
        useMaterial3: true,
      ),
      home: const AwazHomePage(),
    );
  }
}
