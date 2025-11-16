from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional


class SuggestionRequest(BaseModel):
    transcript: str = Field(..., description="Transkrip percakapan lengkap")


class SuggestionResponse(BaseModel):
    suggestions: List[str] = Field(..., description="Daftar saran tindak lanjut")


class InitialQuestionResponse(BaseModel):
    question: str = Field(..., description="Pertanyaan pembuka berdasarkan gambar")


class VideoPromptResponse(BaseModel):
    prompt: str = Field(
        ..., description="Prompt untuk AI generasi video berdasarkan gambar"
    )


class VideoJobResponse(BaseModel):
    job_id: str = Field(..., description="Job ID untuk tracking video generation")
    prompt: str = Field(..., description="Prompt yang digunakan untuk generate video")
    status: str = Field(
        ..., description="Status job: queued, running, completed, error"
    )
    progress: int = Field(default=0, description="Progress percentage (0-100)")


class VideoStatusResponse(BaseModel):
    job_id: str = Field(..., description="Job ID")
    status: str = Field(
        ..., description="Status job: queued, running, completed, error"
    )
    progress: int = Field(default=0, description="Progress percentage (0-100)")
    video_url: Optional[str] = Field(
        None, description="URL untuk download video jika sudah selesai"
    )
    error: Optional[str] = Field(None, description="Error message jika status error")
