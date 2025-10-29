from __future__ import annotations
import os
from functools import lru_cache

class Config:
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"

    def __init__(self) -> None:
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
        if not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is required.")

@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()