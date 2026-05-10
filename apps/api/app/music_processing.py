from __future__ import annotations

import json
import shutil
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

from app.config import Settings, settings
from app.job_store import converted_dir, output_dir, read_job, result_urls, update_job

VIOLIN_LOWEST_MIDI = 55  # G3
DURATION_TO_QUARTERS = {
    "whole": 4.0,
    "half": 2.0,
    "quarter": 1.0,
    "eighth": 0.5,
    "sixteenth": 0.25,
}


class PipelineError(RuntimeError):
    def __init__(self, user_message: str, detail: str | None = None) -> None:
        super().__init__(detail or user_message)
        self.user_message = user_message
        self.detail = detail or user_message


class DependencyMissingError(PipelineError):
    pass


def convert_audio_to_wav(input_path: Path, wav_path: Path) -> Path:
    if shutil.which("ffmpeg") is None:
        raise DependencyMissingError("ffmpeg is not installed or not available in PATH.")

    wav_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-ac",
        "1",
        "-ar",
        "44100",
        str(wav_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise PipelineError(
            "Audio conversion failed. Try a shorter or clearer supported audio file.",
            result.stderr[-2000:] if result.stderr else "ffmpeg returned a non-zero exit code.",
        )
    if not wav_path.exists() or wav_path.stat().st_size == 0:
        raise PipelineError("Audio conversion failed. ffmpeg did not create a WAV file.")
    return wav_path


def run_basic_pitch(wav_path: Path, midi_path: Path) -> Path:
    try:
        from basic_pitch.inference import ICASSP_2022_MODEL_PATH, predict_and_save
    except Exception as exc:  # pragma: no cover - depends on local optional dependency
        raise DependencyMissingError(
            "Spotify Basic Pitch is not installed or could not be imported.",
            str(exc),
        ) from exc

    midi_path.parent.mkdir(parents=True, exist_ok=True)
    model_path = settings.basic_pitch_model_path or ICASSP_2022_MODEL_PATH
    log_path = midi_path.parent / "basic_pitch.log"
    basic_pitch_dir = midi_path.parent / "basic_pitch"
    if basic_pitch_dir.exists():
        shutil.rmtree(basic_pitch_dir)
    basic_pitch_dir.mkdir(parents=True, exist_ok=True)

    log_buffer = StringIO()
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            predict_and_save(
                [str(wav_path)],
                str(basic_pitch_dir),
                save_midi=True,
                sonify_midi=False,
                save_model_outputs=False,
                save_notes=False,
                model_or_model_path=model_path,
            )
    except Exception as exc:  # pragma: no cover - depends on model runtime
        log_path.write_text(f"{log_buffer.getvalue()}\n{exc}", encoding="utf-8")
        raise PipelineError(
            "Basic Pitch transcription failed. Try a shorter or clearer melody recording.",
            str(exc),
        ) from exc
    log_path.write_text(log_buffer.getvalue(), encoding="utf-8")

    generated_midis = sorted(list(basic_pitch_dir.glob("*.mid")) + list(basic_pitch_dir.glob("*.midi")))
    if not generated_midis:
        raise PipelineError("Basic Pitch did not produce a MIDI file.")

    shutil.copyfile(generated_midis[0], midi_path)
    if not midi_path.exists() or midi_path.stat().st_size == 0:
        raise PipelineError("Basic Pitch produced an empty MIDI file.")
    return midi_path


def estimate_tempo(score: Any) -> int:
    try:
        marks = list(score.recurse().getElementsByClass("MetronomeMark"))
        for mark in marks:
            if mark.number:
                return int(round(float(mark.number)))
    except Exception:
        pass
    return 90


def estimate_key(score: Any) -> str:
    try:
        analyzed = score.analyze("key")
        tonic = analyzed.tonic.name.replace("-", "b")
        mode = "minor" if analyzed.mode == "minor" else "major"
        return f"{tonic} {mode}"
    except Exception:
        return "C major"


def duration_label_from_quarters(quarter_length: float) -> str:
    if quarter_length <= 0:
        return "sixteenth"
    return min(
        DURATION_TO_QUARTERS,
        key=lambda label: abs(DURATION_TO_QUARTERS[label] - float(quarter_length)),
    )


def duration_seconds_from_label(label: str, tempo_bpm: int) -> float:
    return DURATION_TO_QUARTERS.get(label, 1.0) * 60.0 / max(tempo_bpm, 1)


def parse_midi_to_notes(midi_path: Path) -> tuple[list[dict[str, Any]], str, int]:
    try:
        from music21 import chord, converter, note as m21_note
    except Exception as exc:
        raise DependencyMissingError("music21 is not installed or could not be imported.", str(exc)) from exc

    try:
        score = converter.parse(str(midi_path))
    except Exception as exc:
        raise PipelineError("MIDI parsing failed. The transcription output could not be read.", str(exc)) from exc

    tempo_bpm = estimate_tempo(score)
    detected_key = estimate_key(score)
    seconds_per_quarter = 60.0 / max(tempo_bpm, 1)
    extracted: list[dict[str, Any]] = []

    for element in score.recurse():
        if isinstance(element, chord.Chord):
            pitch_obj = max(element.pitches, key=lambda item: item.midi)
        elif isinstance(element, m21_note.Note):
            pitch_obj = element.pitch
        else:
            continue

        try:
            offset_quarters = float(element.getOffsetInHierarchy(score))
        except Exception:
            offset_quarters = float(element.offset)

        quarter_length = max(float(element.duration.quarterLength), 0.25)
        start_time = max(0.0, offset_quarters * seconds_per_quarter)
        duration_seconds = quarter_length * seconds_per_quarter
        velocity = getattr(element.volume, "velocity", None)
        confidence = 1.0 if velocity is None else max(0.0, min(float(velocity) / 127.0, 1.0))

        extracted.append(
            {
                "start_time": round(start_time, 4),
                "end_time": round(start_time + duration_seconds, 4),
                "pitch": pitch_obj.nameWithOctave.replace("-", "b"),
                "midi_number": int(pitch_obj.midi),
                "duration_seconds": round(duration_seconds, 4),
                "duration_label": duration_label_from_quarters(quarter_length),
                "confidence": round(confidence, 3),
            }
        )

    extracted.sort(key=lambda item: (item["start_time"], item["midi_number"]))
    if not extracted:
        raise PipelineError("No melody notes were detected in the generated MIDI.")

    for index, item in enumerate(extracted, start=1):
        item["index"] = index
    return extracted, detected_key, tempo_bpm


def normalize_key_name(key_name: str | None) -> str:
    if not key_name:
        return "C major"
    parts = key_name.strip().split()
    if len(parts) == 1:
        return f"{parts[0]} major"
    return f"{parts[0]} {parts[1].lower()}"


def make_music21_key(key_module: Any, key_name: str | None) -> Any:
    normalized = normalize_key_name(key_name)
    tonic, mode = normalized.split()[:2]
    return key_module.Key(tonic, mode)


def build_score_from_notes(
    notes: list[dict[str, Any]],
    *,
    tempo_bpm: int,
    detected_key: str,
    meter: str = "4/4",
) -> Any:
    try:
        from music21 import clef, duration, instrument, key, metadata, note, stream, tempo
        from music21 import meter as m21_meter
    except Exception as exc:
        raise DependencyMissingError("music21 is not installed or could not be imported.", str(exc)) from exc

    score = stream.Score(id="MelodySheetViolin")
    score.insert(0, metadata.Metadata())
    score.metadata.title = "MelodySheet Violin Melody"
    score.metadata.composer = "Generated from uploaded audio"

    part = stream.Part(id="Violin")
    part.insert(0, instrument.Violin())
    part.insert(0, clef.TrebleClef())
    part.insert(0, tempo.MetronomeMark(number=int(tempo_bpm)))
    part.insert(0, m21_meter.TimeSignature(meter))
    try:
        part.insert(0, make_music21_key(key, detected_key))
    except Exception:
        part.insert(0, key.Key("C", "major"))

    for item in sorted(notes, key=lambda note_item: (note_item["start_time"], note_item["midi_number"])):
        try:
            generated_note = note.Note(item["pitch"])
        except Exception as exc:
            raise PipelineError(f"Invalid pitch '{item['pitch']}' in edited notes.", str(exc)) from exc

        generated_note.duration = duration.Duration(
            DURATION_TO_QUARTERS.get(item.get("duration_label"), 1.0)
        )
        # The editable JSON keeps detected start/end times for playback and auditing.
        # For notation export, use a quantized monophonic sequence so MusicXML stays readable.
        part.append(generated_note)

    score.insert(0, part)
    return score


def write_musicxml_and_midi(
    notes: list[dict[str, Any]],
    *,
    musicxml_path: Path,
    midi_path: Path,
    tempo_bpm: int,
    detected_key: str,
    meter: str = "4/4",
) -> None:
    score = build_score_from_notes(
        notes,
        tempo_bpm=tempo_bpm,
        detected_key=detected_key,
        meter=meter,
    )
    musicxml_path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(musicxml_path))
    score.write("midi", fp=str(midi_path))


def scale_degree_for_pitch(pitch_name: str, detected_key: str) -> tuple[str, int]:
    try:
        from music21 import key, pitch

        key_obj = make_music21_key(key, detected_key)
        pitch_obj = pitch.Pitch(pitch_name)
        degree, accidental = key_obj.getScaleDegreeAndAccidentalFromPitch(pitch_obj)
        if degree is None:
            return "?", 0
        accidental_text = ""
        if accidental is not None and accidental.alter:
            if accidental.alter > 0:
                accidental_text = "#" * int(abs(accidental.alter))
            elif accidental.alter < 0:
                accidental_text = "b" * int(abs(accidental.alter))
        tonic_octave = 4
        octave = (pitch_obj.octave or tonic_octave) - tonic_octave
        return f"{accidental_text}{degree}", octave
    except Exception:
        return "?", 0


def generate_numbered_notation(
    notes: list[dict[str, Any]],
    *,
    detected_key: str,
    tempo_bpm: int,
    meter: str = "4/4",
) -> dict[str, Any]:
    numbered_notes = []
    for item in notes:
        degree, octave = scale_degree_for_pitch(item["pitch"], detected_key)
        numbered_notes.append(
            {
                "index": item["index"],
                "pitch_name": item["pitch"],
                "scale_degree": degree,
                "octave": octave,
                "duration": item["duration_label"],
                "start_time": item["start_time"],
                "end_time": item["end_time"],
                "confidence": item.get("confidence", 1.0),
            }
        )

    tonic = normalize_key_name(detected_key).split()[0]
    return {
        "key": tonic,
        "meter": meter,
        "tempo": int(tempo_bpm),
        "notes": numbered_notes,
    }


def has_violin_range_warning(notes: list[dict[str, Any]]) -> bool:
    return any(int(item["midi_number"]) < VIOLIN_LOWEST_MIDI for item in notes)


def violin_range_message(notes: list[dict[str, Any]]) -> str | None:
    if has_violin_range_warning(notes):
        return "Some detected notes are below standard violin range. You may need to transpose or correct them."
    return None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def postprocess_midi_to_outputs(
    midi_path: Path,
    outputs_path: Path,
    *,
    source_midi_already_final: bool = True,
) -> dict[str, Any]:
    outputs_path.mkdir(parents=True, exist_ok=True)
    notes, detected_key, tempo_bpm = parse_midi_to_notes(midi_path)
    musicxml_path = outputs_path / "melody.musicxml"
    final_midi_path = outputs_path / "melody.mid"
    notes_path = outputs_path / "notes.json"
    numbered_path = outputs_path / "numbered.json"

    if not source_midi_already_final:
        shutil.copyfile(midi_path, final_midi_path)

    write_musicxml_and_midi(
        notes,
        musicxml_path=musicxml_path,
        midi_path=final_midi_path,
        tempo_bpm=tempo_bpm,
        detected_key=detected_key,
    )
    write_json(notes_path, {"notes": notes})
    write_json(
        numbered_path,
        generate_numbered_notation(notes, detected_key=detected_key, tempo_bpm=tempo_bpm),
    )

    required = [final_midi_path, musicxml_path, notes_path, numbered_path]
    missing = [path.name for path in required if not path.exists() or path.stat().st_size == 0]
    if missing:
        raise PipelineError(f"Post-processing failed. Missing output files: {', '.join(missing)}")

    return {
        "detected_key": normalize_key_name(detected_key).split()[0],
        "estimated_tempo": int(tempo_bpm),
        "note_count": len(notes),
        "violin_range_warning": has_violin_range_warning(notes),
        "violin_range_message": violin_range_message(notes),
    }


def normalize_edited_notes(notes: list[dict[str, Any]], *, tempo_bpm: int) -> list[dict[str, Any]]:
    try:
        from music21 import pitch
    except Exception as exc:
        raise DependencyMissingError("music21 is not installed or could not be imported.", str(exc)) from exc

    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(sorted(notes, key=lambda note_item: note_item["start_time"]), start=1):
        pitch_obj = pitch.Pitch(item["pitch"])
        duration_label = item.get("duration_label", "quarter")
        duration_seconds = duration_seconds_from_label(duration_label, tempo_bpm)
        start_time = max(0.0, float(item["start_time"]))
        normalized.append(
            {
                "index": index,
                "start_time": round(start_time, 4),
                "end_time": round(start_time + duration_seconds, 4),
                "pitch": pitch_obj.nameWithOctave.replace("-", "b"),
                "midi_number": int(pitch_obj.midi),
                "duration_seconds": round(duration_seconds, 4),
                "duration_label": duration_label,
                "confidence": round(float(item.get("confidence", 1.0)), 3),
            }
        )
    return normalized


def regenerate_from_notes(
    job_id: str,
    notes: list[dict[str, Any]],
    config: Settings = settings,
) -> dict[str, Any]:
    metadata = update_job(job_id, config, status="postprocessing", progress=85, error=None)
    result = metadata.get("result") or {}
    input_info = metadata.get("input") or {}
    extension = input_info.get("extension", "wav")
    tempo_bpm = int(result.get("estimated_tempo") or 90)
    detected_key = normalize_key_name(result.get("detected_key") or "C major")
    outputs_path = output_dir(job_id, config)

    normalized_notes = normalize_edited_notes(notes, tempo_bpm=tempo_bpm)
    write_musicxml_and_midi(
        normalized_notes,
        musicxml_path=outputs_path / "melody.musicxml",
        midi_path=outputs_path / "melody.mid",
        tempo_bpm=tempo_bpm,
        detected_key=detected_key,
    )
    write_json(outputs_path / "notes.json", {"notes": normalized_notes})
    write_json(
        outputs_path / "numbered.json",
        generate_numbered_notation(
            normalized_notes,
            detected_key=detected_key,
            tempo_bpm=tempo_bpm,
        ),
    )

    result_update = {
        **result_urls(job_id, extension),
        "detected_key": normalize_key_name(detected_key).split()[0],
        "estimated_tempo": tempo_bpm,
        "note_count": len(normalized_notes),
        "violin_range_warning": has_violin_range_warning(normalized_notes),
        "violin_range_message": violin_range_message(normalized_notes),
    }
    update_job(job_id, config, status="completed", progress=100, error=None, result=result_update)
    return result_update


def process_job(job_id: str, config: Settings = settings) -> None:
    try:
        metadata = read_job(job_id, config)
        input_info = metadata["input"]
        extension = input_info["extension"]
        original_path = config.storage_path / "uploads" / job_id / f"original.{extension}"
        wav_path = converted_dir(job_id, config) / "input.wav"
        midi_path = output_dir(job_id, config) / "melody.mid"

        update_job(job_id, config, status="converting", progress=20, error=None)
        convert_audio_to_wav(original_path, wav_path)

        update_job(job_id, config, status="transcribing", progress=45, error=None)
        run_basic_pitch(wav_path, midi_path)

        update_job(job_id, config, status="postprocessing", progress=75, error=None)
        result_update = postprocess_midi_to_outputs(midi_path, output_dir(job_id, config))
        result_update.update(result_urls(job_id, extension))
        update_job(job_id, config, status="completed", progress=100, error=None, result=result_update)
    except PipelineError as exc:
        update_job(job_id, config, status="failed", progress=100, error=exc.user_message)
    except Exception as exc:  # pragma: no cover - defensive final guard
        update_job(
            job_id,
            config,
            status="failed",
            progress=100,
            error=f"Unexpected processing error: {exc}",
        )
