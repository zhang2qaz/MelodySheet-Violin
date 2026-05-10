from __future__ import annotations

import os
from pathlib import Path


class Settings:
    def __init__(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        storage_env = os.getenv("MELODYSHEET_STORAGE_PATH")
        self.storage_path = (
            Path(storage_env).expanduser().resolve()
            if storage_env
            else repo_root / "storage"
        )
        self.max_upload_bytes = int(
            os.getenv("MELODYSHEET_MAX_UPLOAD_BYTES", str(50 * 1024 * 1024))
        )
        self.allowed_file_types = {
            ext.strip().lower().lstrip(".")
            for ext in os.getenv("MELODYSHEET_ALLOWED_FILE_TYPES", "mp3,wav,m4a").split(",")
            if ext.strip()
        }
        self.auto_process = os.getenv("MELODYSHEET_AUTO_PROCESS", "true").lower() not in {
            "0",
            "false",
            "no",
        }
        self.cors_origins = [
            origin.strip()
            for origin in os.getenv(
                "MELODYSHEET_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
            ).split(",")
            if origin.strip()
        ]
        self.basic_pitch_model_path = os.getenv("MELODYSHEET_BASIC_PITCH_MODEL_PATH")


settings = Settings()
