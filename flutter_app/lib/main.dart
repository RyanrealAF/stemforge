import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';
import 'package:file_picker/file_picker.dart';
import 'package:just_audio/just_audio.dart';

void main() {
  runApp(const StemForgeApp());
}

class StemForgeApp extends StatelessWidget {
  const StemForgeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'StemForge',
      theme: ThemeData.dark().copyWith(
        primaryColor: Colors.orange,
        scaffoldBackgroundColor: const Color(0xFF09090B),
      ),
      home: const StemForgeHome(),
    );
  }
}

class StemForgeHome extends StatefulWidget {
  const StemForgeHome({super.key});

  @override
  State<StemForgeHome> createState() => _StemForgeHomeState();
}

class _StemForgeHomeState extends State<StemForgeHome> {
  final String kApiBase = "https://Ryanrealaf-stemforge.hf.space";
  bool isProcessing = false;
  double progress = 0;
  String? jobId;
  final AudioPlayer _player = AudioPlayer();

  Future<void> _pickAndUpload() async {
    FilePickerResult? result = await FilePicker.platform.pickFiles(type: FileType.audio);
    if (result != null) {
      setState(() {
        isProcessing = true;
        progress = 0;
      });

      var request = http.MultipartRequest('POST', Uri.parse('$kApiBase/upload'));
      request.files.add(await http.MultipartFile.fromPath('file', result.files.single.path!));
      
      var response = await request.send();
      if (response.statusCode == 200) {
        var data = jsonDecode(await response.stream.bytesToString());
        jobId = data['job_id'];
        _startPolling();
      } else {
        setState(() => isProcessing = false);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Upload failed')));
      }
    }
  }

  void _startPolling() {
    Timer.periodic(const Duration(seconds: 3), (timer) async {
      if (jobId == null) {
        timer.cancel();
        return;
      }

      var res = await http.get(Uri.parse('$kApiBase/status/$jobId'));
      if (res.statusCode == 200) {
        var data = jsonDecode(res.body);
        setState(() {
          progress = data['progress'].toDouble();
        });

        if (data['status'] == 'complete') {
          timer.cancel();
          setState(() => isProcessing = false);
          // In a real app, download and play stems here
        } else if (data['status'] == 'error') {
          timer.cancel();
          setState(() => isProcessing = false);
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error: ${data['error']}')));
        }
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('STEMFORGE', style: TextStyle(fontWeight: FontWeight.black, fontStyle: FontStyle.italic)),
        backgroundColor: Colors.transparent,
        elevation: 0,
      ),
      body: Center(
        child: isProcessing 
          ? Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const CircularProgressIndicator(color: Colors.orange),
                const SizedBox(height: 20),
                Text('Processing: ${progress.toInt()}%', style: const TextStyle(fontSize: 18)),
              ],
            )
          : ElevatedButton.icon(
              onPressed: _pickAndUpload,
              icon: const Icon(Icons.upload),
              label: const Text('LOAD TRACK'),
              style: ElevatedButton.styleFrom(backgroundColor: Colors.orange, foregroundColor: Colors.black),
            ),
      ),
    );
  }
}
