from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import settings
from app.job_store import create_job_metadata, ensure_job_dirs, output_dir
from app.music_processing import (
    DependencyMissingError,
    convert_audio_to_wav,
    generate_numbered_notation,
    postprocess_midi_to_outputs,
)


def test_ffmpeg_missing_failure(monkeypatch, tmp_path):
    monkeypatch.setattr("app.music_processing.shutil.which", lambda _: None)

    with pytest.raises(DependencyMissingError) as exc:
        convert_audio_to_wav(tmp_path / "input.mp3", tmp_path / "input.wav")

    assert "ffmpeg is not installed" in exc.value.user_message


def test_numbered_notation_generation():
    notes = [
        {
            "index": 1,
            "start_time": 0.0,
            "end_time": 0.5,
            "pitch": "C4",
            "midi_number": 60,
            "duration_seconds": 0.5,
            "duration_label": "quarter",
            "confidence": 0.9,
        },
        {
            "index": 2,
            "start_time": 0.5,
            "end_time": 1.0,
            "pitch": "D4",
            "midi_number": 62,
            "duration_seconds": 0.5,
            "duration_label": "quarter",
            "confidence": 0.8,
        },
    ]

    numbered = generate_numbered_notation(notes, detected_key="C major", tempo_bpm=120)

    assert numbered["key"] == "C"
    assert numbered["meter"] == "4/4"
    assert numbered["tempo"] == 120
    assert numbered["notes"][0]["scale_degree"] == "1"
    assert numbered["notes"][1]["scale_degree"] == "2"


def test_midi_to_musicxml_conversion(tmp_path):
    from music21 import clef, instrument, note, stream, tempo
    from music21 import meter as m21_meter

    score = stream.Score()
    part = stream.Part()
    part.insert(0, instrument.Violin())
    part.insert(0, clef.TrebleClef())
    part.insert(0, tempo.MetronomeMark(number=90))
    part.insert(0, m21_meter.TimeSignature("4/4"))
    part.append(note.Note("C4", quarterLength=1.0))
    part.append(note.Note("D4", quarterLength=1.0))
    score.insert(0, part)

    midi_path = tmp_path / "source.mid"
    score.write("midi", fp=str(midi_path))

    outputs = tmp_path / "outputs"
    result = postprocess_midi_to_outputs(midi_path, outputs, source_midi_already_final=False)

    assert result["note_count"] == 2
    assert (outputs / "melody.mid").exists()
    assert (outputs / "melody.musicxml").exists()
    assert (outputs / "notes.json").exists()
    assert (outputs / "numbered.json").exists()

    notes_payload = json.loads((outputs / "notes.json").read_text(encoding="utf-8"))
    assert notes_payload["notes"][0]["pitch"] == "C4"


def test_regenerate_endpoint(client):
    job_id = "a" * 32
    ensure_job_dirs(job_id, settings)
    (settings.storage_path / "uploads" / job_id / "original.wav").write_bytes(b"fake")
    create_job_metadata(
        job_id,
        original_filename="original.wav",
        extension="wav",
        size_bytes=4,
        config=settings,
    )

    response = client.post(
        f"/api/jobs/{job_id}/regenerate",
        json={
            "notes": [
                {
                    "index": 1,
                    "start_time": 0.0,
                    "end_time": 0.5,
                    "pitch": "C4",
                    "midi_number": 60,
                    "duration_seconds": 0.5,
                    "duration_label": "quarter",
                    "confidence": 0.87,
                },
                {
                    "index": 2,
                    "start_time": 0.5,
                    "end_time": 1.0,
                    "pitch": "F3",
                    "midi_number": 53,
                    "duration_seconds": 0.5,
                    "duration_label": "quarter",
                    "confidence": 0.75,
                },
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["result"]["note_count"] == 2
    assert payload["result"]["violin_range_warning"] is True
    assert "below standard violin range" in payload["result"]["violin_range_message"]
    assert Path(output_dir(job_id, settings) / "melody.musicxml").exists()
