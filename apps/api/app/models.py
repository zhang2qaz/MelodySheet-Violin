from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


JobStatus = Literal[
    "uploaded",
    "converting",
    "preprocessing",
    "transcribing",
    "postprocessing",
    "completed",
    "failed",
]

VALID_DURATION_LABELS = {"whole", "half", "quarter", "eighth", "sixteenth"}


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus


class DetectedInstrument(BaseModel):
    instrument: str
    confidence: float
    source: Optional[str] = None
    reason: Optional[str] = None


class TrackOutput(BaseModel):
    musicxml: Optional[str] = None
    midi: Optional[str] = None


class JobResult(BaseModel):
    original_audio_url: Optional[str] = None
    midi_url: Optional[str] = None
    musicxml_url: Optional[str] = None
    numbered_json_url: Optional[str] = None
    notes_url: Optional[str] = None
    detected_key: Optional[str] = None
    estimated_tempo: Optional[int] = None
    estimated_meter: Optional[str] = None
    note_count: Optional[int] = None
    target_instrument: Optional[str] = None
    filtered_note_count: int = 0
    preprocessing_summary: Optional[str] = None
    transcription_method: Optional[str] = None
    detected_instruments: List[DetectedInstrument] = Field(default_factory=list)
    demucs_stems_used: List[str] = Field(default_factory=list)
    per_track_outputs: Dict[str, TrackOutput] = Field(default_factory=dict)
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
            raise ValueError(f"duration_label 必须是以下值之一：{allowed}")
        return normalized

    @field_validator("pitch")
    @classmethod
    def normalize_pitch(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_times(self) -> "EditableNote":
        if self.end_time <= self.start_time:
            raise ValueError("end_time 必须大于 start_time")
        return self


class RegenerateRequest(BaseModel):
    notes: List[EditableNote] = Field(min_length=1)


class RegenerateResponse(BaseModel):
    job_id: str
    status: JobStatus
    result: JobResult
