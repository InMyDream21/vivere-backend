from __future__ import annotations

# import google.generativeai as genai
from google import genai
from google.genai import types
from app.config import get_config

_config = get_config()
client = genai.Client()


def generate_suggestions(prompt: str) -> str:
    response = client.models.generate_content(
        model=_config.GEMINI_MODEL, contents=prompt
    )
    return getattr(response, "text", "") or "<no_suggestion>"


def generate_suggestions_for_image(image_bytes: bytes, content_type: str) -> str:
    image_content = types.Part.from_bytes(data=image_bytes, mime_type=content_type)

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
            """,
        ],
    )
    return getattr(response, "text", "") or "<no_suggestion>"


def generate_video_prompt_from_image(image_bytes: bytes, content_type: str) -> str:
    """
    Generate a video generation prompt from an image using Gemini.

    Args:
        image_bytes: Raw image bytes
        content_type: MIME type of the image

    Returns:
        str: A prompt for image-to-video generation AI
    """
    image_content = types.Part.from_bytes(data=image_bytes, mime_type=content_type)

    response = client.models.generate_content(
        model=_config.GEMINI_MODEL,
        contents=[
            image_content,
            """Analyze this image and create an action-oriented prompt for an image-to-video generation AI (like Runway, Pika, or Sora) to bring this memory to life.

Focus on DIRECT ACTIONS and CAMERA MOVEMENTS, not static descriptions. Use action verbs and dynamic instructions like:
- Camera movements: "The camera slowly pans...", "A gentle zoom focuses on...", "The shot tracks..."
- Character actions: "smiles warmly", "turns toward", "reaches out", "laughs"
- Environmental dynamics: "leaves gently sway", "rain falls softly", "light shifts"
- Temporal progression: "gradually", "slowly", "as the moment unfolds"

Avoid static scene descriptions. Instead, describe what HAPPENS and how the camera MOVES to capture it.

IMPORTANT: Return ONLY the video generation prompt itself. Do not include:
- Explanations of why it works
- Instructions on how to use it
- Emojis or formatting like ### or 🎬
- Any commentary or additional context

Just return the direct, action-oriented prompt that would be fed into the video AI tool.""",
        ],
    )
    return getattr(response, "text", "") or ""
