from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import Settings, settings


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_storage_dirs(config: Settings = settings) -> None:
    for name in ("uploads", "converted", "outputs", "jobs"):
        (config.storage_path / name).mkdir(parents=True, exist_ok=True)


def job_file(job_id: str, config: Settings = settings) -> Path:
    return config.storage_path / "jobs" / f"{job_id}.json"


def upload_dir(job_id: str, config: Settings = settings) -> Path:
    return config.storage_path / "uploads" / job_id


def converted_dir(job_id: str, config: Settings = settings) -> Path:
    return config.storage_path / "converted" / job_id


def output_dir(job_id: str, config: Settings = settings) -> Path:
    return config.storage_path / "outputs" / job_id


def ensure_job_dirs(job_id: str, config: Settings = settings) -> None:
    upload_dir(job_id, config).mkdir(parents=True, exist_ok=True)
    converted_dir(job_id, config).mkdir(parents=True, exist_ok=True)
    output_dir(job_id, config).mkdir(parents=True, exist_ok=True)
    (config.storage_path / "jobs").mkdir(parents=True, exist_ok=True)


def result_urls(job_id: str, extension: str) -> dict[str, Any]:
    return {
        "original_audio_url": f"/api/files/{job_id}/original.{extension}",
        "midi_url": f"/api/files/{job_id}/melody.mid",
        "musicxml_url": f"/api/files/{job_id}/melody.musicxml",
        "numbered_json_url": f"/api/files/{job_id}/numbered.json",
        "notes_url": f"/api/files/{job_id}/notes.json",
    }


def create_job_metadata(
    job_id: str,
    *,
    original_filename: str,
    extension: str,
    size_bytes: int,
    target_instrument: str = "violin",
    config: Settings = settings,
) -> dict[str, Any]:
    created_at = now_iso()
    metadata: dict[str, Any] = {
        "job_id": job_id,
        "status": "uploaded",
        "progress": 0,
        "error": None,
        "created_at": created_at,
        "updated_at": created_at,
        "input": {
            "original_filename": original_filename,
            "extension": extension,
            "size_bytes": size_bytes,
            "target_instrument": target_instrument,
        },
        "result": {
            **result_urls(job_id, extension),
            "detected_key": None,
            "estimated_tempo": None,
            "note_count": None,
            "target_instrument": target_instrument,
            "filtered_note_count": 0,
            "preprocessing_summary": None,
            "violin_range_warning": False,
            "violin_range_message": None,
        },
    }
    write_job(metadata, config)
    return metadata


def read_job(job_id: str, config: Settings = settings) -> dict[str, Any]:
    path = job_file(job_id, config)
    if not path.exists():
        raise FileNotFoundError(job_id)
    return json.loads(path.read_text(encoding="utf-8"))


def write_job(metadata: dict[str, Any], config: Settings = settings) -> None:
    ensure_storage_dirs(config)
    path = job_file(metadata["job_id"], config)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    temp_path.replace(path)


def update_job(job_id: str, config: Settings = settings, **updates: Any) -> dict[str, Any]:
    metadata = read_job(job_id, config)
    for key, value in updates.items():
        if key == "result" and isinstance(value, dict):
            metadata.setdefault("result", {}).update(value)
        else:
            metadata[key] = value
    metadata["updated_at"] = now_iso()
    write_job(metadata, config)
    return metadata
