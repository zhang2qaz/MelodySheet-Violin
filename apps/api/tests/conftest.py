from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.job_store import ensure_storage_dirs
from main import app


@pytest.fixture()
def client(tmp_path):
    settings.storage_path = tmp_path / "storage"
    settings.auto_process = False
    ensure_storage_dirs(settings)
    return TestClient(app)
