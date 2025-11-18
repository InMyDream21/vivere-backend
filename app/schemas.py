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


class VideoPromptTestResponse(BaseModel):
    prompt: str = Field(
        ..., description="Generated video prompt for testing (without running workflow)"
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


# class QueueTaskInfo(BaseModel):
#     prompt_id: str = Field(..., description="Prompt/Job ID")
#     job_id: str = Field(..., description="Job ID (same as prompt_id)")
#     number: Optional[int] = Field(None, description="Queue position number")
#     status: str = Field(
#         default="unknown", description="Status job: queued, running, completed, error"
#     )
#     progress: int = Field(default=0, description="Progress percentage (0-100)")
#     node_progress: Optional[str] = Field(
#         None, description="Node progress in format 'X/Y' (e.g., '5/20 nodes')"
#     )
#     elapsed_time: Optional[str] = Field(
#         None, description="Elapsed time since job started (e.g., '1h 23m 45s')"
#     )
#     duration_seconds: Optional[float] = Field(
#         None, description="Generation duration in seconds (if completed)"
#     )
#     video_url: Optional[str] = Field(
#         None, description="URL untuk download video jika sudah selesai"
#     )
#     error: Optional[str] = Field(None, description="Error message jika status error")

#     @classmethod
#     def from_prompt_id(cls, prompt_id: str, number: Optional[int] = None):
#         """Create QueueTaskInfo from prompt_id"""
#         return cls(prompt_id=prompt_id, job_id=prompt_id, number=number)


# class QueueStatusResponse(BaseModel):
#     running: List[QueueTaskInfo] = Field(
#         default_factory=list, description="Tasks currently running"
#     )
#     pending: List[QueueTaskInfo] = Field(
#         default_factory=list, description="Tasks pending in queue"
#     )
#     total_running: int = Field(default=0, description="Total number of running tasks")
#     total_pending: int = Field(default=0, description="Total number of pending tasks")


class CancelTasksResponse(BaseModel):
    success: bool = Field(..., description="Whether cancellation was successful")
    message: str = Field(..., description="Status message")
    interrupted: bool = Field(
        default=False, description="Whether running task was interrupted"
    )
    cleared: bool = Field(
        default=False, description="Whether pending queue was cleared"
    )


class GenerationHistoryItem(BaseModel):
    job_id: str = Field(..., description="Job/Prompt ID")
    status: str = Field(
        ..., description="Status: completed, running, error, or unknown"
    )
    progress: int = Field(default=0, description="Progress percentage (0-100)")
    prompt: Optional[str] = Field(
        None, description="Prompt text used for video generation"
    )
    duration_seconds: Optional[float] = Field(
        None, description="Generation duration in seconds"
    )
    video_filename: Optional[str] = Field(None, description="Generated video filename")
    video_url: Optional[str] = Field(
        None, description="URL to download video if completed"
    )
    error: Optional[str] = Field(None, description="Error message if status is error")


class GenerationHistoryResponse(BaseModel):
    total: int = Field(..., description="Total number of generation jobs")
    jobs: List[GenerationHistoryItem] = Field(
        ..., description="List of generation jobs"
    )

class VideoGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Prompt untuk generasi video")

class VideoGenerationResponse(BaseModel):
    """Schema for the video generation request body."""
    video_url: str  # URL of the image to start the video from
    prompt: str     # Text prompt describing the video's content

class VideoGenerationStatus(BaseModel):
    """Schema for the video generation status response."""
    status: str
    video_url: Optional[str] = None
    operation_id: str
    video_bytes: Optional[bytes] = None