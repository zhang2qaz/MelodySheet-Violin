"""Optional MT3 (Multi-Track Multi-Instrument) transcription backend.

MT3 is Google's transformer model for polyphonic transcription, originally
published in 2021. The reference implementation requires TensorFlow + JAX
+ a 500MB checkpoint, which we keep OUT of the default install — it would
balloon the Windows installer from ~150MB to ~700MB.

This module detects whether MT3 (or its open-source successor YourMT3+) is
available in the venv and exposes a single `transcribe_with_mt3()` function.
Falls through to basic-pitch (existing default) when the model isn't installed.

To enable MT3 locally:
    pip install yourmt3 mt3-transcribe   # or follow upstream install docs

The pipeline calls this only when MELODYSHEET_USE_MT3=1 is set, so the
default path stays light.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def is_mt3_available() -> bool:
    if os.getenv("MELODYSHEET_USE_MT3") != "1":
        return False
    try:
        # Either of these packages provides an MT3-compatible interface.
        import importlib
        for module_name in ("yourmt3", "mt3", "mt3_transcribe"):
            spec = importlib.util.find_spec(module_name)
            if spec is not None:
                return True
    except Exception:
        pass
    return False


def transcribe_with_mt3(audio_path: Path) -> list[dict[str, Any]]:
    """Transcribe a polyphonic audio file with MT3. Returns notes in our
    standard schema. Raises ImportError if MT3 isn't installed.
    """
    if not is_mt3_available():
        raise ImportError("MT3 not available (install yourmt3 + set MELODYSHEET_USE_MT3=1)")

    # YourMT3+ provides this API:
    #   from yourmt3 import predict
    #   notes = predict(str(audio_path))
    # Returns list of {start, end, pitch (MIDI), program (instrument)}.
    try:
        from yourmt3 import predict  # type: ignore[import-not-found]
    except ImportError as exc:
        raise ImportError(
            "Install yourmt3 to enable MT3 polyphonic transcription: "
            "pip install yourmt3"
        ) from exc

    raw_notes = predict(str(audio_path))
    converted: list[dict[str, Any]] = []
    for note in raw_notes:
        start = float(note.get("start", note.get("start_time", 0.0)))
        end = float(note.get("end", note.get("end_time", 0.0)))
        midi = int(note.get("pitch", note.get("midi_number", 60)))
        program = int(note.get("program", 0))  # General MIDI program number
        if end <= start:
            continue
        converted.append({
            "start_time": round(start, 4),
            "end_time": round(end, 4),
            "duration_seconds": round(end - start, 4),
            "midi_number": midi,
            "pitch": _midi_to_name(midi),
            "duration_label": "quarter",
            "confidence": 0.9,
            "mt3_program": program,
        })
    converted.sort(key=lambda item: (item["start_time"], item["midi_number"]))
    for index, note in enumerate(converted, start=1):
        note["index"] = index
    return converted


def _midi_to_name(midi: int) -> str:
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    return f"{names[midi % 12]}{midi // 12 - 1}"


def nmf_preprocess(audio: Any, sample_rate: int, n_components: int = 8) -> list[Any]:
    """Decompose polyphonic audio into N source components via NMF.

    For each component we return the reconstructed time-domain signal. Running
    basic-pitch on each component independently and merging gives noticeably
    better polyphonic results than running it once on the mix — especially on
    piano + accompaniment.
    """
    try:
        import librosa
        import numpy as np
    except Exception:
        return []
    if audio is None or len(audio) == 0:
        return []

    n_fft = 2048
    hop_length = 512
    stft = librosa.stft(audio, n_fft=n_fft, hop_length=hop_length)
    magnitude, phase = librosa.magphase(stft)
    W, H = librosa.decompose.decompose(magnitude, n_components=n_components, sort=True)
    components: list[Any] = []
    for k in range(n_components):
        comp_magnitude = np.outer(W[:, k], H[k, :])
        comp_stft = comp_magnitude * phase
        comp_audio = librosa.istft(comp_stft, hop_length=hop_length, n_fft=n_fft)
        components.append(comp_audio)
    return components
