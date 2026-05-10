#!/usr/bin/env python3
from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path


NOTES_HZ = [
    261.63,  # C4
    293.66,  # D4
    329.63,  # E4
    392.00,  # G4
    349.23,  # F4
    329.63,  # E4
    293.66,  # D4
    261.63,  # C4
]


def write_test_wav(path: Path, sample_rate: int = 44100) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    duration_per_note = 0.45
    amplitude = 0.35
    frames = []

    for frequency in NOTES_HZ:
        total = int(sample_rate * duration_per_note)
        for i in range(total):
            envelope = min(1.0, i / 800.0, (total - i) / 800.0)
            value = amplitude * envelope * math.sin(2 * math.pi * frequency * i / sample_rate)
            frames.append(struct.pack("<h", int(value * 32767)))

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(frames))


def main() -> None:
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("storage/uploads/test-melody.wav")
    write_test_wav(output)
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
