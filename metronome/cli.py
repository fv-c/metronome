"""Command-line interface for metronome."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .engine import (DEFAULT_PITCHES, DEFAULT_VELOCITIES, generate_track,
                     parse_int_list, write_midi, write_wav)


def main(argv: list[str] | None = None) -> int:
    # Windows pipes may use a legacy code page even when paths are Unicode.
    # Escape unsupported characters in messages without changing the real paths.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    parser = argparse.ArgumentParser(
        prog="metronome", description="Genera tracce di metronomo MIDI e/o WAV."
    )
    parser.add_argument("--meter", required=True, help="Metro, ad es. 4/4, 3/4, 6/8")
    parser.add_argument("--bpm", type=float, required=True, help="Tempo in BPM")
    parser.add_argument("--mode", choices=("click", "percussion"), default="click",
                        help="Click sintetici o beat con campioni Freesound (default click)")
    parser.add_argument("--subdivision", type=int, default=1,
                        help="Colpi per unità del denominatore, da 1 a 32 (default 1)")
    duration = parser.add_mutually_exclusive_group(required=True)
    duration.add_argument("--bars", help="Durata in battute (anche frazionario, es. 3/2)")
    duration.add_argument("--seconds", type=float, help="Durata esatta in secondi")
    parser.add_argument("--pattern", help="Pesi ciclici, es. '(2 1 1 1 1 1 1 1)'")
    parser.add_argument("--tempo-unit", default="1/4",
                        help="Valore di nota a cui si riferisce BPM (default 1/4; es. 3/8)")
    parser.add_argument("--pitches", default=" ".join(map(str, DEFAULT_PITCHES)),
                        help="Note MIDI per livelli 0,1,2,3...; solo modalità click")
    parser.add_argument("--velocities", default=" ".join(map(str, DEFAULT_VELOCITIES)),
                        help="Velocity MIDI per livelli 0,1,2,3... (crescenti)")
    parser.add_argument("--sample-rate", type=int, default=44100, help="Hz WAV (default 44100)")
    parser.add_argument("--click-ms", type=float, default=90,
                        help="Durata click WAV e note MIDI in ms; i campioni WAV usano la coda naturale")
    parser.add_argument("--format", choices=("both", "midi", "wav"), default="both")
    parser.add_argument("--output", default="metronome", help="Prefisso dei file di output")
    args = parser.parse_args(argv)

    try:
        track = generate_track(
            meter=args.meter, bpm=args.bpm, bars=args.bars, seconds=args.seconds,
            pattern=args.pattern, tempo_unit=args.tempo_unit,
            pitches=parse_int_list(args.pitches), velocities=parse_int_list(args.velocities),
            mode=args.mode, subdivision=args.subdivision,
        )
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if args.format in ("both", "midi"):
            path = Path(f"{destination}.mid")
            write_midi(path, track, click_ms=args.click_ms)
            outputs.append(path)
        if args.format in ("both", "wav"):
            path = Path(f"{destination}.wav")
            write_wav(path, track, sample_rate=args.sample_rate, click_ms=args.click_ms)
            outputs.append(path)
    except (ValueError, OverflowError, OSError) as exc:
        parser.error(str(exc))

    print(f"{track.mode} | Metro {track.numerator}/{track.denominator} | {track.bpm:g} BPM "
          f"(unità {track.tempo_unit}) | {len(track.events)} battiti | "
          f"{track.duration_seconds:.3f} s")
    for path in outputs:
        print(f"Creato: {path}")
    return 0
