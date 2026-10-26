"""Build sdist/wheel and test a clean, offline installation on any supported OS.

Run with `python scripts/check_package.py` after installing the `build` tool.
The runtime environment receives only the wheel, with no extra dependencies.
"""

from fractions import Fraction
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
import wave


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="metronome-package-") as directory:
        work = Path(directory)
        dist = work / "dist"
        # The default build produces the wheel from the sdist, testing both.
        subprocess.run([sys.executable, "-m", "build", "--outdir", str(dist), str(root)],
                       cwd=work, check=True)
        wheel = next(dist.glob("*.whl"))
        if not wheel.name.endswith("-py3-none-any.whl"):
            raise RuntimeError(f"Expected a platform-independent wheel: {wheel.name}")
        environment = work / "ambiente prova 日本語"
        venv.EnvBuilder(with_pip=True).create(environment)
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        console = scripts / ("metronome.exe" if os.name == "nt" else "metronome")
        subprocess.run([str(python), "-I", "-m", "pip", "install", "--no-deps",
                        "--no-index", str(wheel)], cwd=work, check=True)
        subprocess.run([str(python), "-I", "-m", "unittest", "discover",
                        "-s", str(root / "tests"), "-v"], cwd=work, check=True)

        # Check the generated Windows .exe / POSIX console entry point as well
        # as `python -m`, outside the checkout and with a restricted pipe codec.
        for mode in ("click", "percussion"):
            outputs = []
            for name, command in (("module", [str(python), "-I", "-m", "metronome"]),
                                  ("console", [str(console)])):
                base = work / "audio à 日本語" / f"{name} {mode}"
                result = subprocess.run(
                    command + ["--mode", mode, "--meter", "7/8", "--bpm", "90",
                               "--bars", "1", "--subdivision", "2", "--pattern",
                               "3 0 1", "--output", str(base)],
                    cwd=work, env=dict(os.environ, PYTHONIOENCODING="cp1252"),
                    capture_output=True,
                )
                if result.returncode:
                    raise RuntimeError(result.stderr.decode("cp1252", errors="replace"))
                midi = base.with_suffix(".mid")
                wav = base.with_suffix(".wav")
                if not midi.read_bytes().startswith(b"MThd"):
                    raise RuntimeError("Invalid MIDI export")
                with wave.open(str(wav)) as source:
                    expected = round(Fraction(7, 8) / Fraction(1, 4) * Fraction(60, 90) * 44100)
                    if (source.getnchannels(), source.getsampwidth(), source.getnframes()) != (1, 2, expected):
                        raise RuntimeError("Invalid WAV format or duration")
                outputs.append((midi.read_bytes(), wav.read_bytes()))
            if outputs[0] != outputs[1]:
                raise RuntimeError(f"Module and console exports differ in {mode} mode")
        print("PASS: platform-independent wheel; clean install; installed test suite; "
              "module and console exports in both modes; Unicode paths and cp1252 pipes")


if __name__ == "__main__":
    main()
