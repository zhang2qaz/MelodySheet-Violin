from __future__ import annotations

import json

from app.config import settings
from app.job_store import job_file


def test_upload_rejects_unsupported_file_type(client):
    response = client.post(
        "/api/jobs",
        files={"file": ("song.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert "不支持的文件类型" in response.json()["detail"]


def test_upload_rejects_empty_file(client):
    response = client.post(
        "/api/jobs",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "上传的文件为空。"


def test_upload_creates_job_and_metadata(client):
    response = client.post(
        "/api/jobs",
        files={"file": ("melody.wav", b"RIFFfake-data", "audio/wav")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "uploaded"
    assert payload["job_id"]

    metadata_path = job_file(payload["job_id"], settings)
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["status"] == "uploaded"
    assert metadata["input"]["original_filename"] == "melody.wav"
    assert metadata["input"]["extension"] == "wav"
    assert metadata["input"]["size_bytes"] == len(b"RIFFfake-data")
    assert metadata["input"]["target_instrument"] == "violin"
    assert metadata["result"]["target_instrument"] == "violin"


def test_upload_accepts_target_instrument(client):
    response = client.post(
        "/api/jobs",
        data={"target_instrument": "flute"},
        files={"file": ("melody.wav", b"RIFFfake-data", "audio/wav")},
    )

    assert response.status_code == 200
    metadata_path = job_file(response.json()["job_id"], settings)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["input"]["target_instrument"] == "flute"
    assert metadata["result"]["target_instrument"] == "flute"


def test_get_job_returns_metadata(client):
    create_response = client.post(
        "/api/jobs",
        files={"file": ("melody.m4a", b"m4a-data", "audio/mp4")},
    )
    job_id = create_response.json()["job_id"]

    response = client.get(f"/api/jobs/{job_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == job_id
    assert payload["status"] == "uploaded"
    assert payload["result"]["original_audio_url"].endswith("/original.m4a")
