from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List

class SuggestionRequest(BaseModel):
    transcript: str = Field(..., description="Transkrip percakapan lengkap")
    # locale: str = Field(..., description="Kode lokal untuk saran bahasa")
    # max_suggestions: int = Field(default=4, ge=1, le=8, description="Jumlah maksimum saran yang diinginkan")

class SuggestionResponse(BaseModel):
    suggestions: List[str] = Field(..., description="Daftar saran tindak lanjut")
