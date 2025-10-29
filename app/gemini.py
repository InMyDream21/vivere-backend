from __future__ import annotations
# import google.generativeai as genai
from google import genai
from google.genai import types
from app.config import get_config

_config = get_config()
client = genai.Client()

def generate_suggestions(prompt: str) -> str:
    response = client.models.generate_content(
        model=_config.GEMINI_MODEL,
        contents=prompt
        )
    return getattr(response, "text", "") or "<no_suggestion>"