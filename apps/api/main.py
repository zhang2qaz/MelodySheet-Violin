from __future__ import annotations

import re
import shutil
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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
from app.models import JobCreateResponse, JobStatusResponse, RegenerateRequest, RegenerateResponse
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
    allowed_outputs = {"melody.mid", "melody.musicxml", "numbered.json", "notes.json"}

    if filename == allowed_upload:
        path = upload_dir(job_id, settings) / filename
    elif filename in allowed_outputs:
        path = output_dir(job_id, settings) / filename
    else:
        raise HTTPException(status_code=404, detail="未找到文件。")

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
        )
    except PipelineError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc

    return RegenerateResponse(job_id=job_id, status="completed", result=result)
