from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


JobStatus = Literal[
    "uploaded",
    "converting",
    "transcribing",
    "postprocessing",
    "completed",
    "failed",
]

VALID_DURATION_LABELS = {"whole", "half", "quarter", "eighth", "sixteenth"}


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobResult(BaseModel):
    original_audio_url: Optional[str] = None
    midi_url: Optional[str] = None
    musicxml_url: Optional[str] = None
    numbered_json_url: Optional[str] = None
    notes_url: Optional[str] = None
    detected_key: Optional[str] = None
    estimated_tempo: Optional[int] = None
    note_count: Optional[int] = None
    violin_range_warning: bool = False
    violin_range_message: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    error: Optional[str] = None
    result: Optional[JobResult] = None


class EditableNote(BaseModel):
    index: int = Field(ge=1)
    start_time: float = Field(ge=0)
    end_time: float = Field(gt=0)
    pitch: str = Field(min_length=2, max_length=8)
    midi_number: int = Field(ge=0, le=127)
    duration_seconds: float = Field(gt=0)
    duration_label: str
    confidence: float = Field(default=1.0, ge=0, le=1)

    @field_validator("duration_label")
    @classmethod
    def validate_duration_label(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in VALID_DURATION_LABELS:
            allowed = ", ".join(sorted(VALID_DURATION_LABELS))
            raise ValueError(f"duration_label must be one of: {allowed}")
        return normalized

    @field_validator("pitch")
    @classmethod
    def normalize_pitch(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_times(self) -> "EditableNote":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be greater than start_time")
        return self


class RegenerateRequest(BaseModel):
    notes: List[EditableNote] = Field(min_length=1)


class RegenerateResponse(BaseModel):
    job_id: str
    status: JobStatus
    result: JobResult
