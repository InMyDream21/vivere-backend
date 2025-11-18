from __future__ import annotations

# import google.generativeai as genai
from google import genai
from google.genai import types
from google.genai.types import GenerateVideosConfig, Image
from app.config import get_config
from app.schemas import VideoGenerationStatus
from pathlib import Path

VIDEO_OUTPUT_DIR = Path("generated_videos")  # or your media path
VIDEO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_config = get_config()
client = genai.Client()

job_statuses = {}


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
            Buat 1 pertanyaan singkat (hanya 1 kalimat berisi maksimum 8 kata per kalimat) yang jelas dan mudah dipahami untuk memulai percakapan dengan orang dengan demensia (OdD) berdasarkan gambar ini. 
            Gunakan Bahasa Indonesia yang santai, tidak berkonotasi negatif, jelas, singkat, dan mudah dipahami. 
            Hindari menanyakan hal-hal yang sangat rumit, 
            Fokus pada hal-hal positif tentang kegiatan yang ada di gambar, kenangan bahagia di gambar, atau pengalaman sehari-hari yang sederhana. 
            Hindari pertanyaan yang terlalu umum. 
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


def generate_video_from_image(image, content_type):
    operation = client.models.generate_videos(
        model="veo-3.1-generate-preview",
        # prompt=prompt,
        image= Image(image_bytes=image, mime_type=content_type),
        config= GenerateVideosConfig(
            aspect_ratio="16:9",
            enhance_prompt=True,
        )
    )
    print(f"operation: {operation}")
    
    operation_id = operation.name.rsplit("/", 1)[-1]
    print(f"Generated video operation ID: {operation_id}")
    if operation_id is None:
        raise RuntimeError("generate_videos returned an operation with no name")
    job_statuses[operation_id] = {
        "status": "running",
        "video_url": None,
        "error": None,
        "operation": operation,
    }

    return VideoGenerationStatus(status="running", video_url=None, operation_id=operation_id)

def check_for_video_completion(operation_id: str) -> VideoGenerationStatus:
    # if operation_id not in job_statuses:
    #     raise HTTPException(status_code=404, detail="Operation ID not found.")
    try:
        # Check the status of the long-running operation
        operation = job_statuses.get(operation_id)
        operation = client.operations.get(operation=operation["operation"])
        print(f"operation status: {operation}")

        if operation.done:
            # 1. Get the bytes from the response
            generated_video = operation.response.generated_videos[0].video

            # adjust this attribute based on actual SDK field name:
            video_bytes = generated_video.video_bytes  # or .data / .content

            # 2. Decide an output path
            output_path = VIDEO_OUTPUT_DIR / f"{operation_id}.mp4"

            # 3. Write bytes to disk
            with open(output_path, "wb") as f:
                f.write(video_bytes)

            # 4. Turn that into a URL (depends on how you serve static files)
            # For example, if you're mounting /static to generated_videos:
            final_url = f"/static/{operation_id}.mp4"

            job_statuses[operation_id].update({
                "status": "COMPLETED",
                "video_url": final_url,
            })

            return VideoGenerationStatus(
                status="COMPLETED",
                operation_id=operation_id,
                video_url=final_url,
                video_bytes=video_bytes
            )

        else:
            return VideoGenerationStatus(
                status="IN_PROGRESS",
                operation_id=operation_id,
                video_url=None
            )

    except Exception as e:
        raise RuntimeError(f"Error checking operation status: {str(e)}")
