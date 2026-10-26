"""CLI encoding, filesystem and resource regressions, including Windows pipes."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

from metronome import generate_track, write_midi, write_wav


class PortabilityTests(unittest.TestCase):
    def test_cli_unicode_paths_with_redirected_output(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in ("click", "percussion"):
                for encoding in ("ascii", "cp1252"):
                    with self.subTest(mode=mode, encoding=encoding):
                        base = Path(directory) / "prove audio à 日本語" / f"{mode} {encoding}"
                        result = subprocess.run(
                            [sys.executable, "-m", "metronome", "--mode", mode,
                             "--meter", "7/8", "--bpm", "90", "--bars", "1",
                             "--subdivision", "2", "--pattern", "3 0 1",
                             "--output", str(base)],
                            env=dict(os.environ, PYTHONIOENCODING=encoding),
                            capture_output=True,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr.decode(encoding))
                        self.assertIn(b"Creato:", result.stdout)
                        self.assertTrue(base.with_suffix(".mid").read_bytes().startswith(b"MThd"))
                        with wave.open(str(base.with_suffix(".wav"))) as source:
                            self.assertEqual(source.getnframes(), 102900)

    def test_cli_help_with_ascii_output(self):
        result = subprocess.run(
            [sys.executable, "-m", "metronome", "--help"],
            env=dict(os.environ, PYTHONIOENCODING="ascii"), capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("ascii"))
        self.assertIn(b"--subdivision", result.stdout)

    def test_cli_error_with_ascii_output(self):
        result = subprocess.run(
            [sys.executable, "-m", "metronome", "--meter", "4/4",
             "--bpm", "0", "--bars", "1"],
            env=dict(os.environ, PYTHONIOENCODING="ascii"), capture_output=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn(b"BPM", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_export_releases_files_for_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode in ("click", "percussion"):
                with self.subTest(mode=mode):
                    track = generate_track(mode=mode, meter="4/4", bpm=120, bars=1)
                    midi = Path(directory) / "beat.mid"
                    wav = Path(directory) / "beat.wav"
                    write_midi(midi, track)
                    write_wav(wav, track)
                    expected = (midi.read_bytes(), wav.read_bytes())
                    write_midi(midi, track)
                    write_wav(wav, track)
                    self.assertEqual((midi.read_bytes(), wav.read_bytes()), expected)
                    midi.unlink()
                    wav.unlink()


if __name__ == "__main__":
    unittest.main()
