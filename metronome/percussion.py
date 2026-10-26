"""Meter-based low percussion kit and bundled CC0 Freesound samples."""

from array import array
from importlib.resources import files
import sys
import wave

DRUM_SAMPLES = {36: "kick.wav", 45: "low_tom.wav", 47: "mid_tom.wav"}


def percussion_note(index: int, numerator: int, denominator: int, subdivision: int) -> int:
    """Repeat the kit orchestration each bar, independently of accent weights.

    Compound meters group in threes; simple even meters in twos. Odd meters
    above three begin with a group of three followed by groups of two.
    """
    position = index % (numerator * subdivision)
    if position == 0:
        return 36
    beat, offbeat = divmod(position, subdivision)
    if offbeat:
        return 47
    if numerator % 3 == 0 and (denominator >= 8 or numerator == 3):
        group_start = beat % 3 == 0
    elif numerator % 2 == 0:
        group_start = beat % 2 == 0
    else:
        group_start = beat >= 3 and (beat - 3) % 2 == 0
    return 45 if group_start else 47


def load_sample(note: int, sample_rate: int) -> list[float]:
    """Read a bundled mono PCM16 sample and linearly resample it if necessary."""
    resource = files("metronome").joinpath("samples", DRUM_SAMPLES[note])
    with resource.open("rb") as stream, wave.open(stream, "rb") as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError(f"Campione non valido: {resource.name}")
        original_rate = source.getframerate()
        pcm = array("h")
        pcm.frombytes(source.readframes(source.getnframes()))
    if sys.byteorder != "little":
        pcm.byteswap()
    samples = [value / 32768.0 for value in pcm]
    if sample_rate == original_rate:
        return samples
    count = max(1, round(len(samples) * sample_rate / original_rate))
    result = []
    for i in range(count):
        position = min(i * original_rate / sample_rate, len(samples) - 1)
        left = int(position)
        right = min(left + 1, len(samples) - 1)
        fraction = position - left
        result.append(samples[left] * (1 - fraction) + samples[right] * fraction)
    return result
