from __future__ import annotations

import os
import re
import shutil
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.job_store import (
    create_job_metadata,
    ensure_job_dirs,
    ensure_storage_dirs,
    job_file,
    output_dir,
    read_job,
    upload_dir,
)
from app.models import (
    JobCreateResponse,
    JobStatusResponse,
    RegenerateRequest,
    RegenerateResponse,
    UrlImportRequest,
)
from app.music_processing import PipelineError, TARGET_INSTRUMENT_PROFILES, process_job, regenerate_from_notes


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage_dirs(settings)
    yield


app = FastAPI(title="MelodySheet Violin API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1].lower()


def validate_job_id(job_id: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=404, detail="未找到处理任务。")
    return job_id


def validate_target_instrument(target_instrument: str) -> str:
    normalized = (target_instrument or "violin").strip().lower()
    if normalized not in TARGET_INSTRUMENT_PROFILES:
        allowed = ", ".join(sorted(TARGET_INSTRUMENT_PROFILES))
        raise HTTPException(status_code=400, detail=f"不支持的目标乐器。可选项：{allowed}。")
    return normalized


async def save_upload_file(file: UploadFile, destination: Path) -> int:
    destination.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with destination.open("wb") as handle:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > settings.max_upload_bytes:
                handle.close()
                destination.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"文件过大。最大允许大小为 {settings.max_upload_bytes} 字节。",
                )
            handle.write(chunk)

    if size == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="上传的文件为空。")
    return size


@app.post("/api/jobs", response_model=JobCreateResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    target_instrument: str = Form("violin"),
) -> JobCreateResponse:
    extension = extract_extension(file.filename)
    if extension not in settings.allowed_file_types:
        allowed = ", ".join(sorted(settings.allowed_file_types))
        raise HTTPException(status_code=400, detail=f"不支持的文件类型。支持格式：{allowed}。")

    normalized_target = validate_target_instrument(target_instrument)

    job_id = uuid.uuid4().hex
    ensure_job_dirs(job_id, settings)
    destination = upload_dir(job_id, settings) / f"original.{extension}"

    try:
        size_bytes = await save_upload_file(file, destination)
        create_job_metadata(
            job_id,
            original_filename=file.filename or f"original.{extension}",
            extension=extension,
            size_bytes=size_bytes,
            target_instrument=normalized_target,
            config=settings,
        )
    except HTTPException:
        shutil.rmtree(upload_dir(job_id, settings), ignore_errors=True)
        shutil.rmtree(output_dir(job_id, settings), ignore_errors=True)
        job_file(job_id, settings).unlink(missing_ok=True)
        raise

    if settings.auto_process:
        background_tasks.add_task(process_job, job_id, settings)

    return JobCreateResponse(job_id=job_id, status="uploaded")


_ALLOWED_URL_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    "bilibili.com", "www.bilibili.com", "m.bilibili.com",
    "b23.tv",
    "soundcloud.com", "m.soundcloud.com",
    "vimeo.com",
}


def _validate_url(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL 必须以 http:// 或 https:// 开头。")
    host = (parsed.netloc or "").lower().split(":")[0]
    if host not in _ALLOWED_URL_HOSTS:
        allowed = ", ".join(sorted(_ALLOWED_URL_HOSTS))
        raise HTTPException(
            status_code=400,
            detail=f"暂不支持该网站。支持：{allowed}",
        )
    return url.strip()


def _download_with_ytdlp(url: str, dest_path: Path) -> None:
    """Download audio-only from a video URL via yt-dlp. Writes m4a/mp3/webm
    to `dest_path` (we keep the extension yt-dlp picked). Throws on failure.
    """
    if shutil.which("yt-dlp") is None and shutil.which("youtube-dl") is None:
        raise HTTPException(
            status_code=500,
            detail="服务器未安装 yt-dlp。请直接上传本地音频文件。",
        )
    binary = "yt-dlp" if shutil.which("yt-dlp") else "youtube-dl"
    import subprocess
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    template = str(dest_path.parent / "original.%(ext)s")
    cmd = [
        binary,
        "-x",                       # extract audio only
        "--audio-format", "m4a",   # prefer m4a (no ffmpeg required for some sources)
        "--audio-quality", "0",
        "--no-playlist",
        "--max-filesize", "200M",
        "--no-warnings",
        "-o", template,
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        snippet = (result.stderr or result.stdout)[-500:]
        raise HTTPException(
            status_code=400,
            detail=f"音频下载失败。{snippet.strip()}",
        )
    # Find the file yt-dlp produced
    candidates = sorted(dest_path.parent.glob("original.*"))
    if not candidates:
        raise HTTPException(status_code=500, detail="yt-dlp 没有输出可用音频。")


@app.post("/api/jobs/from-url", response_model=JobCreateResponse)
async def create_job_from_url(
    background_tasks: BackgroundTasks,
    payload: UrlImportRequest,
) -> JobCreateResponse:
    """Pull audio from a streaming URL (YouTube / Bilibili / SoundCloud / Vimeo)
    via yt-dlp, then route through the same transcription pipeline.
    """
    url = _validate_url(payload.url)
    normalized_target = validate_target_instrument(payload.target_instrument)

    job_id = uuid.uuid4().hex
    ensure_job_dirs(job_id, settings)
    dest_dir = upload_dir(job_id, settings)

    try:
        _download_with_ytdlp(url, dest_dir / "original.placeholder")
    except HTTPException:
        shutil.rmtree(dest_dir, ignore_errors=True)
        shutil.rmtree(output_dir(job_id, settings), ignore_errors=True)
        job_file(job_id, settings).unlink(missing_ok=True)
        raise

    produced = sorted(dest_dir.glob("original.*"))
    if not produced:
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="yt-dlp 完成但找不到下载产物。")
    audio_path = produced[0]
    extension = audio_path.suffix.lstrip(".").lower() or "m4a"
    size_bytes = audio_path.stat().st_size

    create_job_metadata(
        job_id,
        original_filename=f"original.{extension}",
        extension=extension,
        size_bytes=size_bytes,
        target_instrument=normalized_target,
        config=settings,
    )

    if settings.auto_process:
        background_tasks.add_task(process_job, job_id, settings)

    return JobCreateResponse(job_id=job_id, status="uploaded")


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: str) -> JobStatusResponse:
    validate_job_id(job_id)
    try:
        metadata = read_job(job_id, settings)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到处理任务。") from None
    return JobStatusResponse(**metadata)


@app.get("/api/files/{job_id}/{filename}")
def get_file(job_id: str, filename: str) -> FileResponse:
    validate_job_id(job_id)
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=404, detail="未找到文件。")

    try:
        metadata = read_job(job_id, settings)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到处理任务。") from None

    extension = metadata.get("input", {}).get("extension")
    allowed_upload = f"original.{extension}"
    allowed_outputs = {
        "melody.mid", "melody.musicxml", "numbered.json", "notes.json",
        "spectrogram.png", "melody.ly", "melody.abc",
        "chords.json", "tab.json", "tab.txt", "drums.json", "sections.json",
    }

    if filename == allowed_upload:
        path = upload_dir(job_id, settings) / filename
    elif filename in allowed_outputs:
        path = output_dir(job_id, settings) / filename
    else:
        raise HTTPException(status_code=404, detail="未找到文件。")

    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="未找到文件。")
    return FileResponse(path)


@app.get("/api/files/{job_id}/stems/{filename}")
def get_stem_file(job_id: str, filename: str) -> FileResponse:
    validate_job_id(job_id)
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=404, detail="未找到文件。")
    if not filename.endswith(".wav"):
        raise HTTPException(status_code=404, detail="未找到文件。")
    try:
        read_job(job_id, settings)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到处理任务。") from None
    path = output_dir(job_id, settings) / "stems" / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="未找到文件。")
    return FileResponse(path)


@app.get("/api/files/{job_id}/tracks/{filename}")
def get_track_file(job_id: str, filename: str) -> FileResponse:
    validate_job_id(job_id)
    if "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=404, detail="未找到文件。")
    if not (filename.endswith(".musicxml") or filename.endswith(".mid")):
        raise HTTPException(status_code=404, detail="未找到文件。")

    try:
        read_job(job_id, settings)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到处理任务。") from None

    path = output_dir(job_id, settings) / "tracks" / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="未找到文件。")
    return FileResponse(path)


@app.post("/api/jobs/{job_id}/regenerate", response_model=RegenerateResponse)
def regenerate_job(job_id: str, payload: RegenerateRequest) -> RegenerateResponse:
    validate_job_id(job_id)
    try:
        read_job(job_id, settings)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="未找到处理任务。") from None

    try:
        result = regenerate_from_notes(
            job_id,
            [note.model_dump() for note in payload.notes],
            settings,
            tempo_override=payload.tempo_bpm,
            key_override=payload.detected_key,
            meter_override=payload.meter,
        )
    except PipelineError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc

    # Record this regeneration as user-correction signal for the profile.
    try:
        from app.user_profile import record_correction
        target = result.get("target_instrument") or "violin"
        record_correction(
            target,
            [note.model_dump() for note in payload.notes],
            detected_key=result.get("detected_key"),
            meter=result.get("estimated_meter"),
            tempo_bpm=result.get("estimated_tempo"),
        )
    except Exception:
        pass

    return RegenerateResponse(job_id=job_id, status="completed", result=result)


@app.get("/api/profile")
def get_profile() -> dict:
    """Return the user's stored preferences. UI displays this so the user
    knows what the system has learned about their style."""
    from app.user_profile import read_profile
    return read_profile()


@app.delete("/api/profile")
def delete_profile(target_instrument: Optional[str] = None) -> dict:
    from app.user_profile import reset_profile
    reset_profile(target_instrument)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Static frontend (used by the Windows installer and any single-process
# deployment). Set MELODYSHEET_WEB_DIR to the directory holding the static
# Next.js export. When unset, look for ../web/out (dev tree) and the
# PyInstaller-bundled "_internal/web" directory.
# ---------------------------------------------------------------------------


def _resolve_web_dir() -> Path | None:
    env = os.getenv("MELODYSHEET_WEB_DIR")
    if env:
        candidate = Path(env).expanduser().resolve()
        return candidate if candidate.exists() else None

    # PyInstaller frozen layout: sys._MEIPASS/web/
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "web"
        if bundled.exists():
            return bundled

    # Dev tree: apps/web/out (after `npm run build` with NEXT_OUTPUT=export)
    repo_dev = Path(__file__).resolve().parents[1] / "web" / "out"
    if repo_dev.exists():
        return repo_dev
    return None


_web_dir = _resolve_web_dir()
if _web_dir is not None:
    # FastAPI's StaticFiles with html=True serves index.html on directory
    # requests. We also add a catch-all that returns index.html for any
    # non-existent path so that client-side routing (e.g. /jobs?id=...)
    # works after a hard refresh.
    @app.get("/", include_in_schema=False)
    def _index() -> FileResponse:
        return FileResponse(_web_dir / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str) -> Response:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="未找到。")
        candidate = (_web_dir / full_path).resolve()
        web_root = _web_dir.resolve()
        if web_root in candidate.parents or candidate == web_root:
            if candidate.is_file():
                return FileResponse(candidate)
            html_candidate = candidate / "index.html"
            if html_candidate.is_file():
                return FileResponse(html_candidate)
            html_sibling = candidate.with_suffix(".html")
            if html_sibling.is_file():
                return FileResponse(html_sibling)
        # Fall back to root index — client-side router handles the path.
        return FileResponse(_web_dir / "index.html")

    # Static asset prefix (Next.js puts hashed bundles under /_next/).
    app.mount("/_next", StaticFiles(directory=str(_web_dir / "_next")), name="next_assets")
