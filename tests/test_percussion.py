"""Percussion scheduling, sampled audio, MIDI and offline CLI integration."""

import array
from fractions import Fraction
import hashlib
from importlib.resources import files
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import wave

from metronome import generate_track, write_midi, write_wav
from test_metronome import midi_messages


def read_wav(path):
    with wave.open(str(path), "rb") as source:
        rate = source.getframerate()
        channels = source.getnchannels()
        width = source.getsampwidth()
        pcm = array.array("h")
        pcm.frombytes(source.readframes(source.getnframes()))
    if sys.byteorder != "little":
        pcm.byteswap()
    return rate, channels, width, pcm


class PercussionSchedulingTests(unittest.TestCase):
    def test_subdivisions_do_not_change_bar_duration(self):
        for subdivision in (1, 2, 3, 4, 7, 32):
            with self.subTest(subdivision=subdivision):
                track = generate_track(mode="percussion", meter="4/4", bpm=120,
                                       bars=2, subdivision=subdivision)
                self.assertEqual(len(track.events), 8 * subdivision)
                self.assertAlmostEqual(track.duration_seconds, 4)
                self.assertAlmostEqual(track.events[1].time, 0.5 / subdivision)

    def test_meter_orchestration_and_compound_grouping(self):
        cases = {
            "1/4": [36],
            "3/4": [36, 47, 47],
            "4/4": [36, 47, 45, 47],
            "5/8": [36, 47, 47, 45, 47],
            "6/8": [36, 47, 47, 45, 47, 47],
            "6/4": [36, 47, 45, 47, 45, 47],
            "7/8": [36, 47, 47, 45, 47, 45, 47],
            "9/8": [36, 47, 47, 45, 47, 47, 45, 47, 47],
        }
        for meter, expected in cases.items():
            with self.subTest(meter=meter):
                track = generate_track(mode="percussion", meter=meter, bpm=90, bars=2)
                self.assertEqual([e.note for e in track.events], expected * 2)

    def test_subdivision_instruments(self):
        track = generate_track(mode="percussion", meter="4/4", bpm=120,
                               bars=1, subdivision=2)
        self.assertEqual([e.note for e in track.events], [36, 47, 47, 47, 45, 47, 47, 47])

    def test_accent_cycle_is_independent_of_bar_and_kit(self):
        track = generate_track(mode="percussion", meter="4/4", bpm=120, bars=2,
                               subdivision=2, pattern="3 0 1")
        self.assertEqual([e.level for e in track.events], ([3, 0, 1] * 6)[:16])
        self.assertEqual(track.events[8].note, 36)
        self.assertEqual(track.events[8].level, 1)
        self.assertEqual(track.events[1].velocity, 48)  # 0 is a quiet hit.

    def test_default_pattern_spans_subdivided_bar(self):
        track = generate_track(mode="percussion", meter="3/4", bpm=90,
                               bars=2, subdivision=2)
        self.assertEqual([e.level for e in track.events], [2, 1, 1, 1, 1, 1] * 2)

    def test_fractional_bars_and_compound_tempo(self):
        track = generate_track(mode="percussion", meter="6/8", bpm=60,
                               tempo_unit="3/8", bars="3/2", subdivision=2)
        self.assertAlmostEqual(track.duration_seconds, 3)
        self.assertEqual(len(track.events), 18)
        self.assertAlmostEqual(track.events[1].time, 1 / 6)

    def test_exact_seconds_excludes_end_boundary(self):
        track = generate_track(mode="percussion", meter="4/4", bpm=120,
                               seconds=1, subdivision=3)
        self.assertEqual(len(track.events), 6)
        self.assertTrue(all(e.time < track.duration_seconds for e in track.events))

    def test_accent_changes_dynamics_without_transposing_kit(self):
        quiet = generate_track(mode="percussion", meter="4/4", bpm=90, bars=1, pattern="0")
        loud = generate_track(mode="percussion", meter="4/4", bpm=90, bars=1, pattern="3")
        self.assertEqual([e.note for e in quiet.events], [e.note for e in loud.events])
        self.assertTrue(all(a.velocity < b.velocity for a, b in zip(quiet.events, loud.events)))

    def test_custom_velocity_levels_without_pitches(self):
        track = generate_track(mode="percussion", meter="4/4", bpm=90, bars=1,
                               velocities=(20, 40, 60, 90, 120), pattern="4 0 2 3")
        self.assertEqual([e.velocity for e in track.events], [120, 20, 60, 90])

    def test_invalid_mode_and_subdivisions(self):
        for kwargs in (dict(mode="drums"), *(dict(subdivision=x) for x in (0, -1, 33, 1.5, True))):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                generate_track(meter="4/4", bpm=120, bars=1, **kwargs)

    def test_click_mode_supports_same_subdivision_grid(self):
        track = generate_track(meter="4/4", bpm=120, bars=1, subdivision=2)
        self.assertEqual(track.mode, "click")
        self.assertEqual(len(track.events), 8)
        self.assertAlmostEqual(track.duration_seconds, 2)
        self.assertEqual(track.events[0].note, 81)


class PercussionExportTests(unittest.TestCase):
    def test_midi_drum_channel_kit_velocity_and_duration(self):
        track = generate_track(mode="percussion", meter="6/8", bpm=60, bars=1,
                               tempo_unit="3/8", subdivision=2, pattern="3 0 1 2")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drums.mid"
            write_midi(path, track)
            messages = midi_messages(path.read_bytes())
        notes = [m for m in messages if m[1] == 0x99]
        self.assertEqual([m[0] for m in notes], [240 * i for i in range(12)])
        self.assertEqual([m[2:] for m in notes], [(e.note, e.velocity) for e in track.events])
        self.assertEqual(len([m for m in messages if m[1] == 0x89]), 12)
        self.assertFalse(any(isinstance(m[1], int) and m[1] & 0xF0 == 0xC0 for m in messages))
        self.assertIn((0, "meta", 0x58, bytes((6, 3, 12, 8))), messages)
        self.assertEqual(messages[-1], (2880, "meta", 0x2F, b""))

    def test_midi_fractional_ticks_do_not_accumulate_drift(self):
        track = generate_track(mode="percussion", meter="7/32", bpm=120,
                               bars=3, subdivision=7)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drums.mid"
            write_midi(path, track)
            messages = midi_messages(path.read_bytes())
        self.assertEqual([m[0] for m in messages if m[1] == 0x99],
                         [round(Fraction(120 * i, 7)) for i in range(147)])
        self.assertEqual(messages[-1][0], 2520)

    def test_bundled_sample_credits_hashes_and_format(self):
        root = files("metronome").joinpath("samples")
        records = json.loads(root.joinpath("sources.json").read_text())
        self.assertEqual({r["file"] for r in records}, {"kick.wav", "low_tom.wav", "mid_tom.wav"})
        for record in records:
            with self.subTest(sample=record["file"]):
                resource = root.joinpath(record["file"])
                self.assertEqual(record["license"], "CC0-1.0")
                self.assertEqual(hashlib.sha256(resource.read_bytes()).hexdigest(), record["sha256"])
                with resource.open("rb") as stream, wave.open(stream) as source:
                    self.assertEqual((source.getframerate(), source.getnchannels(), source.getsampwidth()),
                                     (44100, 1, 2))
                    self.assertGreater(source.getnframes(), 4410)
                    self.assertLessEqual(source.getnframes(), 26460)

    def test_wav_exact_length_and_resampling(self):
        track = generate_track(mode="percussion", meter="7/8", bpm=90,
                               seconds=1.123, subdivision=2)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drums.wav"
            for rate in (8000, 22050, 44100, 48000):
                with self.subTest(rate=rate):
                    write_wav(path, track, sample_rate=rate)
                    actual_rate, channels, width, pcm = read_wav(path)
                    self.assertEqual((actual_rate, channels, width), (rate, 1, 2))
                    self.assertEqual(len(pcm), round(1.123 * rate))
                    self.assertGreater(max(abs(v) for v in pcm), 1000)

    def test_wav_accent_strength(self):
        rms = []
        with tempfile.TemporaryDirectory() as directory:
            for level in range(4):
                track = generate_track(mode="percussion", meter="1/4", bpm=60,
                                       bars=1, pattern=(level,))
                path = Path(directory) / "drums.wav"
                write_wav(path, track)
                pcm = read_wav(path)[3]
                rms.append(math.sqrt(sum(v * v for v in pcm) / len(pcm)))
        self.assertTrue(all(a < b for a, b in zip(rms, rms[1:])))
        self.assertAlmostEqual(rms[-1] / rms[0], 124 / 48, places=3)

    def test_wav_sample_mixing_preserves_tails_across_blocks(self):
        track = generate_track(mode="percussion", meter="4/4", bpm=300,
                               bars=1, subdivision=2, pattern="3 0 1 2")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drums.wav"
            write_wav(path, track, click_ms=1)
            pcm = read_wav(path)[3]
        root = files("metronome").joinpath("samples")
        kit = {note: read_wav(root.joinpath(name))[3] for note, name in
               {36: "kick.wav", 45: "low_tom.wav", 47: "mid_tom.wav"}.items()}
        expected = [0.0] * len(pcm)
        for event in track.events:
            start = round(event.time * 44100)
            for i, value in enumerate(kit[event.note][:len(pcm) - start]):
                expected[start + i] += value / 32768 * event.velocity / 127 * 0.70
        expected_pcm = [round(32767 * max(-1, min(1, v))) for v in expected]
        self.assertEqual(list(pcm), expected_pcm)
        self.assertTrue(any(pcm[4410:8000]))  # Natural tails survive click_ms=1.

    def test_cli_both_formats_with_bundled_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory) / "out" / "beat"
            result = subprocess.run(
                [sys.executable, "-m", "metronome", "--mode", "percussion", "--meter", "5/8",
                 "--bpm", "90", "--bars", "1", "--subdivision", "2", "--pattern", "3 0 1",
                 "--output", str(base)], capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("percussion", result.stdout)
            self.assertTrue(base.with_suffix(".mid").exists())
            self.assertEqual(len(read_wav(base.with_suffix(".wav"))[3]), 73500)

    def test_cli_rejects_invalid_subdivision(self):
        result = subprocess.run(
            [sys.executable, "-m", "metronome", "--mode", "percussion", "--meter", "4/4",
             "--bpm", "120", "--bars", "1", "--subdivision", "0"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("subdivision", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
