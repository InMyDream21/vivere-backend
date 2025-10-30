from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List

class SuggestionRequest(BaseModel):
    transcript: str = Field(..., description="Transkrip percakapan lengkap")

class SuggestionResponse(BaseModel):
    suggestions: List[str] = Field(..., description="Daftar saran tindak lanjut")

class InitialQuestionResponse(BaseModel):
    question: str = Field(..., description="Pertanyaan pembuka berdasarkan gambar")
