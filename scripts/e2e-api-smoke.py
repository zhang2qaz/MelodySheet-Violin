#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import struct
import sys
import time
import uuid
import wave
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT_DIR = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("storage/smoke-test")
EXPECTED_FILES = ["melody.mid", "melody.musicxml", "numbered.json", "notes.json"]


def write_test_wav(path: Path, sample_rate: int = 44100) -> None:
    notes_hz = [261.63, 293.66, 329.63, 392.0, 349.23, 329.63, 293.66, 261.63]
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = []
    for frequency in notes_hz:
        total = int(sample_rate * 0.45)
        for i in range(total):
            envelope = min(1.0, i / 800.0, (total - i) / 800.0)
            value = 0.35 * envelope * math.sin(2 * math.pi * frequency * i / sample_rate)
            frames.append(struct.pack("<h", int(value * 32767)))

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(b"".join(frames))


def request_json(url: str) -> dict:
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def post_file(url: str, path: Path) -> dict:
    boundary = f"----MelodySheet{uuid.uuid4().hex}"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="smoke-test.wav"\r\n',
            b"Content-Type: audio/wav\r\n\r\n",
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str, destination: Path) -> None:
    with urlopen(url, timeout=30) as response:
        destination.write_bytes(response.read())


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample_path = OUT_DIR / "smoke-test.wav"
    write_test_wav(sample_path)

    try:
        created = post_file(f"{API_BASE_URL}/api/jobs", sample_path)
    except HTTPError as exc:
        print(f"Upload failed: HTTP {exc.code} {exc.read().decode('utf-8', errors='replace')}")
        return 1

    job_id = created["job_id"]
    print(f"Created job {job_id}")
    final = None
    for _ in range(90):
        payload = request_json(f"{API_BASE_URL}/api/jobs/{job_id}")
        print(f"{payload['status']} {payload['progress']}%")
        if payload["status"] in {"completed", "failed"}:
            final = payload
            break
        time.sleep(1)

    if not final:
        print("Timed out waiting for job completion.")
        return 1
    if final["status"] != "completed":
        print(json.dumps(final, indent=2))
        return 1

    result = final["result"]
    for filename in EXPECTED_FILES:
        download(f"{API_BASE_URL}/api/files/{job_id}/{filename}", OUT_DIR / filename)

    missing = [filename for filename in EXPECTED_FILES if (OUT_DIR / filename).stat().st_size == 0]
    if missing:
        print(f"Downloaded empty output files: {', '.join(missing)}")
        return 1

    print(json.dumps(result, indent=2))
    print(f"Downloaded outputs to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
