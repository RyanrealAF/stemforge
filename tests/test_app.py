import math
import os
import tempfile
import wave
import unittest

import app


class MidiGenerationTests(unittest.TestCase):
    def write_sine_wav(self, path, frequency=440.0, duration=0.35, sample_rate=8000):
        sample_count = int(sample_rate * duration)
        with wave.open(path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            frames = bytearray()
            for sample_index in range(sample_count):
                value = int(16000 * math.sin(2 * math.pi * frequency * sample_index / sample_rate))
                frames.extend(value.to_bytes(2, byteorder="little", signed=True))
            wav_file.writeframes(bytes(frames))

    def test_creates_midi_for_piano_guitar_and_bass_stems(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            original_output_dir = app.OUTPUT_DIR
            app.OUTPUT_DIR = tmpdir
            job_id = "job-midi"
            stem_dir = os.path.join(tmpdir, job_id, "htdemucs_6s", "song")
            os.makedirs(stem_dir)

            for stem, frequency in {
                "vocals": 220.0,
                "drums": 180.0,
                "bass": 110.0,
                "guitar": 330.0,
                "piano": 440.0,
                "other": 550.0,
            }.items():
                self.write_sine_wav(os.path.join(stem_dir, f"{stem}.wav"), frequency=frequency)

            try:
                midi_files = app.create_midi_outputs(job_id)
                outputs = app.get_separated_outputs(job_id)
            finally:
                app.OUTPUT_DIR = original_output_dir

            self.assertEqual(len(midi_files), 3)
            output_paths = {output["relative_path"] for output in outputs}
            self.assertIn("htdemucs_6s/song/vocals.wav", output_paths)
            self.assertIn("htdemucs_6s/song/drums.wav", output_paths)
            self.assertIn("htdemucs_6s/song/bass.wav", output_paths)
            self.assertIn("htdemucs_6s/song/guitar.wav", output_paths)
            self.assertIn("htdemucs_6s/song/piano.wav", output_paths)
            self.assertIn("htdemucs_6s/song/other.wav", output_paths)
            self.assertIn("htdemucs_6s/song/piano.mid", output_paths)
            self.assertIn("htdemucs_6s/song/guitar.mid", output_paths)
            self.assertIn("htdemucs_6s/song/bass.mid", output_paths)

            for midi_path in midi_files:
                with open(midi_path, "rb") as midi_file:
                    self.assertEqual(midi_file.read(4), b"MThd")


class FrontendServingTests(unittest.TestCase):
    def test_serves_frontend_and_health_check_from_api_origin(self):
        import asyncio
        index_response = asyncio.run(app.serve_frontend())
        self.assertEqual(index_response.status_code, 200)
        self.assertIn("StemForge", index_response.body.decode())
        self.assertIn("resolveApiBase", index_response.body.decode())

        health_response = asyncio.run(app.health_check())
        self.assertEqual(health_response, {"status": "ok"})


if __name__ == "__main__":
    unittest.main()
