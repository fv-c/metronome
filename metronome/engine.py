"""Dependency-free metronome event scheduling, MIDI, and WAV rendering."""

from __future__ import annotations

from array import array
from bisect import bisect_left
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import math
import random
import re
import struct
import sys
import wave

from .percussion import load_sample, percussion_note

DEFAULT_PITCHES = (72, 76, 81, 84)
DEFAULT_VELOCITIES = (48, 76, 101, 124)
TICKS_PER_QUARTER = 960
WOODBLOCK_PROGRAM = 115  # General MIDI instrument 116 (0-based program).


@dataclass(frozen=True)
class Click:
    index: int
    time: float
    level: int
    note: int
    velocity: int


@dataclass(frozen=True)
class Track:
    numerator: int
    denominator: int
    bpm: float
    tempo_unit: Fraction
    duration_seconds: float
    events: tuple[Click, ...]
    mode: str = "click"
    subdivision: int = 1


def parse_int_list(value: str) -> tuple[int, ...]:
    """Accept '2 1 1', '(2 1 1)', '[2,1,1]' or '2,1,1'."""
    text = value.strip()
    if len(text) >= 2 and (text[0], text[-1]) in (("(", ")"), ("[", "]")):
        text = text[1:-1]
    fields = [part for part in re.split(r"[\s,;]+", text.strip()) if part]
    if not fields:
        raise ValueError("La lista non può essere vuota")
    try:
        return tuple(int(part) for part in fields)
    except ValueError as exc:
        raise ValueError("La lista deve contenere soltanto numeri interi") from exc


def parse_meter(meter: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", meter)
    if not match:
        raise ValueError("Il metro deve essere N/D, per esempio 4/4 oppure 6/8")
    numerator, denominator = map(int, match.groups())
    if not 1 <= numerator <= 255:
        raise ValueError("Il numeratore del metro deve essere tra 1 e 255")
    if denominator not in (1, 2, 4, 8, 16, 32):
        raise ValueError("Il denominatore deve essere 1, 2, 4, 8, 16 o 32")
    return numerator, denominator


def _positive_fraction(value: Fraction | str | int, name: str) -> Fraction:
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError, TypeError) as exc:
        raise ValueError(f"{name} deve essere un numero o una frazione positiva") from exc
    if result <= 0:
        raise ValueError(f"{name} deve essere positivo")
    return result


def generate_track(
    *,
    meter: str,
    bpm: float,
    bars: Fraction | str | int | None = None,
    seconds: float | None = None,
    pattern: tuple[int, ...] | list[int] | str | None = None,
    tempo_unit: Fraction | str = "1/4",
    pitches: tuple[int, ...] | list[int] = DEFAULT_PITCHES,
    velocities: tuple[int, ...] | list[int] = DEFAULT_VELOCITIES,
    mode: str = "click",
    subdivision: int = 1,
) -> Track:
    """Generate clicks or a sampled percussion beat with cyclic accent weights.

    BPM refers to tempo_unit (default quarter note). Each denominator-unit has
    `subdivision` equally spaced hits. The accent pattern loops freely; the
    percussion kit repeats with the meter. Weight 0 is quiet, never a rest.
    Exactly one of bars or seconds must be supplied.
    """
    numerator, denominator = parse_meter(meter)
    if mode not in ("click", "percussion"):
        raise ValueError("mode deve essere click oppure percussion")
    if type(subdivision) is not int or not 1 <= subdivision <= 32:
        raise ValueError("subdivision deve essere un intero tra 1 e 32")
    bpm = float(bpm)
    if not math.isfinite(bpm) or bpm <= 0:
        raise ValueError("BPM deve essere un numero positivo e finito")
    unit = _positive_fraction(tempo_unit, "tempo_unit")
    if (bars is None) == (seconds is None):
        raise ValueError("Specificare esattamente uno tra bars e seconds")

    pitches = tuple(pitches)
    velocities = tuple(velocities)
    if len(velocities) < 3:
        raise ValueError("Occorrono almeno 3 livelli di velocity")
    if mode == "click":
        if len(pitches) != len(velocities):
            raise ValueError("Occorrono note e velocity di uguale lunghezza")
        if any(not isinstance(note, int) or not 0 <= note <= 127 for note in pitches):
            raise ValueError("Ogni nota MIDI deve essere un intero tra 0 e 127")
        if any(a >= b for a, b in zip(pitches, pitches[1:])):
            raise ValueError("Le altezze devono crescere con il peso")
    if any(not isinstance(velocity, int) or not 1 <= velocity <= 127 for velocity in velocities):
        raise ValueError("Ogni velocity MIDI deve essere un intero tra 1 e 127")
    if any(a >= b for a, b in zip(velocities, velocities[1:])):
        raise ValueError("Le velocity devono crescere con il peso")

    if pattern is None:
        levels = (2,) + (1,) * (numerator * subdivision - 1)
    elif isinstance(pattern, str):
        levels = parse_int_list(pattern)
    else:
        levels = tuple(pattern)
    if not levels or any(not isinstance(level, int) or not 0 <= level < len(velocities) for level in levels):
        raise ValueError(f"Ogni peso del pattern deve essere un intero tra 0 e {len(velocities) - 1}")

    pulse_seconds = (60.0 / bpm) * float(Fraction(1, denominator * subdivision) / unit)
    if bars is not None:
        bar_count = _positive_fraction(bars, "bars")
        duration = float(bar_count) * numerator * subdivision * pulse_seconds
        count = math.ceil(bar_count * numerator * subdivision)
    else:
        duration = float(seconds)
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("seconds deve essere positivo e finito")
        count = max(1, math.ceil(duration / pulse_seconds - 1e-12))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Durata non valida")
    if count > 2_000_000:
        raise ValueError("Troppi battiti richiesti (massimo 2.000.000)")

    events = tuple(
        Click(i, i * pulse_seconds, levels[i % len(levels)],
              percussion_note(i, numerator, denominator, subdivision) if mode == "percussion"
              else pitches[levels[i % len(levels)]], velocities[levels[i % len(levels)]])
        for i in range(count)
    )
    return Track(numerator, denominator, bpm, unit, duration, events, mode, subdivision)


def _vlq(number: int) -> bytes:
    """Standard MIDI variable-length quantity."""
    if number < 0:
        raise ValueError("Delta MIDI negativo")
    values = [number & 0x7F]
    number >>= 7
    while number:
        values.insert(0, (number & 0x7F) | 0x80)
        number >>= 7
    return bytes(values)


def write_midi(path: str | Path, track: Track, *, click_ms: float = 90.0) -> None:
    """Write type-0 SMF: pitched woodblock or GM drums on channel 10."""
    if not math.isfinite(click_ms) or click_ms <= 0:
        raise ValueError("click_ms deve essere positivo e finito")
    quarter_seconds = (60.0 / track.bpm) * float(Fraction(1, 4) / track.tempo_unit)
    tempo_us = round(quarter_seconds * 1_000_000)
    if not 1 <= tempo_us <= 0xFFFFFF:
        raise ValueError("Il tempo richiesto non è rappresentabile nel file MIDI")
    pulse_ticks = Fraction(TICKS_PER_QUARTER * 4, track.denominator * track.subdivision)
    total_ticks = max(1, round(track.duration_seconds / quarter_seconds * TICKS_PER_QUARTER))
    note_ticks = max(1, round((click_ms / 1000.0) / quarter_seconds * TICKS_PER_QUARTER))
    note_ticks = min(note_ticks, max(1, int(pulse_ticks) - 1))
    clocks_per_click = max(1, round(96 / track.denominator))

    messages: list[tuple[int, int, bytes]] = [
        (0, 0, b"\xff\x03\x09Metronome"),
        (0, 1, b"\xff\x51\x03" + tempo_us.to_bytes(3, "big")),
        (0, 2, bytes((0xFF, 0x58, 4, track.numerator, track.denominator.bit_length() - 1,
                      clocks_per_click, 8))),
    ]
    channel = 9 if track.mode == "percussion" else 0
    if track.mode == "click":
        messages.append((0, 3, bytes((0xC0, WOODBLOCK_PROGRAM))))
    for click in track.events:
        start = round(click.index * pulse_ticks)
        if start >= total_ticks:
            continue
        stop = min(total_ticks, start + note_ticks)
        stop = max(start + 1, stop)
        messages.append((start, 5, bytes((0x90 | channel, click.note, click.velocity))))
        messages.append((stop, 4, bytes((0x80 | channel, click.note, 0))))
    messages.sort(key=lambda item: (item[0], item[1]))
    midi_track = bytearray()
    previous = 0
    for at, _, content in messages:
        midi_track.extend(_vlq(at - previous))
        midi_track.extend(content)
        previous = at
    midi_track.extend(_vlq(max(total_ticks, previous) - previous))
    midi_track.extend(b"\xff\x2f\x00")

    Path(path).write_bytes(
        struct.pack(">4sIHHH", b"MThd", 6, 0, 1, TICKS_PER_QUARTER)
        + b"MTrk" + struct.pack(">I", len(midi_track)) + midi_track
    )


def _woodblock(note: int, velocity: int, frames: int, sample_rate: int, seed: int) -> list[float]:
    """Short inharmonic resonances + attack noise; no soundfont required."""
    fundamental = 440.0 * 2.0 ** ((note - 69) / 12.0)
    rng = random.Random(72413 + seed)
    duration = frames / sample_rate
    voice: list[float] = []
    partials = ((1.0, 0.80, 46.0), (2.42, 0.38, 85.0), (3.71, 0.16, 140.0))
    playable = [(multiple, gain, damping) for multiple, gain, damping in partials
                if fundamental * multiple < 0.45 * sample_rate]
    for i in range(frames):
        t = i / sample_rate
        attack = 1.0 - math.exp(-t / 0.00035)
        fade = (1.0 - t / duration) ** 2
        resonances = sum(
            gain * math.sin(2.0 * math.pi * fundamental * multiple * t)
            * math.exp(-damping * t)
            for multiple, gain, damping in playable
        )
        noise = (rng.random() * 2.0 - 1.0) * 0.32 * math.exp(-260.0 * t)
        voice.append((resonances + noise) * attack * fade * (velocity / 127.0) * 0.70)
    return voice


def write_wav(
    path: str | Path,
    track: Track,
    *,
    sample_rate: int = 44_100,
    click_ms: float = 90.0,
) -> None:
    """Render a mono PCM-16 WAV in blocks without storing the whole file in RAM."""
    if not isinstance(sample_rate, int) or not 8_000 <= sample_rate <= 192_000:
        raise ValueError("sample_rate deve essere tra 8000 e 192000")
    if not math.isfinite(click_ms) or click_ms <= 0:
        raise ValueError("click_ms deve essere positivo e finito")
    total_frames = round(track.duration_seconds * sample_rate)
    if not 1 <= total_frames <= 0xFFFFFFFF // 2 - 22:
        raise ValueError("La durata supera i limiti del WAV PCM-16")
    click_frames = max(1, round(click_ms / 1000.0 * sample_rate))
    templates = {}
    samples = {}
    for click in track.events:
        key = (click.note, click.velocity)
        if key in templates:
            continue
        if track.mode == "percussion":
            if click.note not in samples:
                samples[click.note] = load_sample(click.note, sample_rate)
            templates[key] = [v * (click.velocity / 127.0) * 0.70
                              for v in samples[click.note]]
        else:
            templates[key] = _woodblock(click.note, click.velocity, click_frames,
                                       sample_rate, click.level)
    voice_frames = max((len(voice) for voice in templates.values()), default=0)
    onsets = [round(click.time * sample_rate) for click in track.events]
    block_size = 8192
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        for offset in range(0, total_frames, block_size):
            end = min(total_frames, offset + block_size)
            mix = [0.0] * (end - offset)
            first = bisect_left(onsets, offset - voice_frames + 1)
            last = bisect_left(onsets, end)
            for i in range(first, last):
                onset = onsets[i]
                click = track.events[i]
                clip = templates[(click.note, click.velocity)]
                begin = max(onset, offset)
                finish = min(end, onset + len(clip))
                for j in range(begin, finish):
                    mix[j - offset] += clip[j - onset]
            pcm = array("h", (round(32767.0 * max(-1.0, min(1.0, v))) for v in mix))
            if sys.byteorder != "little":
                pcm.byteswap()
            output.writeframesraw(pcm.tobytes())
