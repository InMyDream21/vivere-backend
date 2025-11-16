from __future__ import annotations
import os
from functools import lru_cache


class Config:
    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"
    COMFYUI_SERVER_URL: str = "http://127.0.0.1:8188"
    COMFYUI_INPUT_DIR: str = ""
    COMFYUI_OUTPUT_DIR: str = ""
    COMFYUI_WORKFLOW_PATH: str = ""
    GLANCES_URL: str = "http://localhost:61208/api/4"

    def __init__(self) -> None:
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
        if not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY environment variable is required.")

        self.COMFYUI_SERVER_URL = os.getenv(
            "COMFYUI_SERVER_URL", "http://127.0.0.1:8188"
        ).strip()
        self.COMFYUI_INPUT_DIR = os.getenv("COMFYUI_INPUT_DIR", "").strip()
        self.COMFYUI_OUTPUT_DIR = os.getenv("COMFYUI_OUTPUT_DIR", "").strip()
        self.COMFYUI_WORKFLOW_PATH = os.getenv("COMFYUI_WORKFLOW_PATH", "").strip()
        self.GLANCES_URL = os.getenv(
            "GLANCES_URL", "http://localhost:61208/api/4"
        ).strip()


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()
