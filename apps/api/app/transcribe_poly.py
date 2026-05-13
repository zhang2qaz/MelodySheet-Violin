from __future__ import annotations

from pathlib import Path
from typing import Any


POLY_THRESHOLDS: dict[str, dict[str, Any]] = {
    "piano": {
        "onset_threshold": 0.55,
        "frame_threshold": 0.34,
        "minimum_note_length": 80,
        "minimum_frequency": 27.5,
        "maximum_frequency": 4200.0,
        "melodia_trick": True,
    },
    "guitar": {
        "onset_threshold": 0.6,
        "frame_threshold": 0.36,
        "minimum_note_length": 100,
        "minimum_frequency": 70.0,
        "maximum_frequency": 1500.0,
        "melodia_trick": True,
    },
}

DEFAULT_POLY_THRESHOLDS = {
    "onset_threshold": 0.5,
    "frame_threshold": 0.3,
    "minimum_note_length": 70,
    "minimum_frequency": 32.7,
    "maximum_frequency": 5000.0,
    "melodia_trick": True,
}


def transcribe_polyphonic_to_notes(
    wav_path: Path,
    target_instrument: str,
) -> list[dict[str, Any]]:
    """Run Basic Pitch with per-instrument tuned thresholds and return note dicts directly.

    Going through `predict` (rather than `predict_and_save`) gives us the raw note events
    so we don't lose information re-parsing a MIDI file, and lets us keep per-note
    confidence directly from the model.
    """
    try:
        from basic_pitch.inference import ICASSP_2022_MODEL_PATH, predict
    except Exception as exc:
        raise RuntimeError(f"Basic Pitch 不可用：{exc}") from exc

    params = {**DEFAULT_POLY_THRESHOLDS, **POLY_THRESHOLDS.get(target_instrument, {})}
    _, _, note_events = predict(
        str(wav_path),
        model_or_model_path=ICASSP_2022_MODEL_PATH,
        onset_threshold=params["onset_threshold"],
        frame_threshold=params["frame_threshold"],
        minimum_note_length=params["minimum_note_length"],
        minimum_frequency=params["minimum_frequency"],
        maximum_frequency=params["maximum_frequency"],
        multiple_pitch_bends=False,
        melodia_trick=params["melodia_trick"],
    )

    notes: list[dict[str, Any]] = []
    for event in note_events:
        # Basic Pitch returns tuples (start_time, end_time, pitch_midi, amplitude, pitch_bend) —
        # we conservatively read by position.
        start_time = float(event[0])
        end_time = float(event[1])
        midi_number = int(event[2])
        amplitude = float(event[3]) if len(event) > 3 else 1.0
        duration_seconds = max(end_time - start_time, 0.05)
        notes.append(
            {
                "start_time": round(start_time, 4),
                "end_time": round(start_time + duration_seconds, 4),
                "pitch": _midi_to_name(midi_number),
                "midi_number": midi_number,
                "duration_seconds": round(duration_seconds, 4),
                "duration_label": "quarter",
                "confidence": round(max(0.0, min(amplitude, 1.0)), 3),
            }
        )
    notes.sort(key=lambda item: (item["start_time"], item["midi_number"]))
    for index, note in enumerate(notes, start=1):
        note["index"] = index
    return notes


def _midi_to_name(midi_number: int) -> str:
    names = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
    name = names[midi_number % 12]
    octave = midi_number // 12 - 1
    return f"{name}{octave}"
