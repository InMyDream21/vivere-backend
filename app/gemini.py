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

def generate_suggestions_for_image(image_bytes: bytes, content_type: str) -> str:
    image_content = types.Part.from_bytes(
        data=image_bytes,
        mime_type=content_type
    )

    response = client.models.generate_content(
        model=_config.GEMINI_MODEL,
        contents=[
            image_content,
            """
            Buat 1 pertanyaan pembuka singkat (hanya 1 kalimat) yang ramah dan mudah dipahami untuk memulai percakapan dengan orang dengan demensia (OdD) berdasarkan gambar ini.
            Gunakan Bahasa Indonesia yang sopan, empatik, kalem, dan mudah dipahami.
            Hindari menguji ingatan atau topik medis.
            Fokus pada hal-hal positif, kenangan bahagia, atau pengalaman sehari-hari yang sederhana.
            Format keluaran hanya dalam JSON: {\"question\": ... hanya 1 item ...}
            """
        ]
    )
    return getattr(response, "text", "") or "<no_suggestion>"