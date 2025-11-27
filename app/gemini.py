from __future__ import annotations

# import google.generativeai as genai
from google import genai
from google.genai import types
from google.genai.types import GenerateVideosConfig, Image
from app.config import get_config
from app.schemas import VideoGenerationStatus
from pathlib import Path

import threading
import time


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


def _poll_and_download_video(operation, operation_id: str) -> None:
    """
    Background worker:
    - polls the operation
    - waits until done
    - downloads & saves the video
    - updates job_statuses
    """
    try:
        while not operation.done:
            print(f"[{operation_id}] Waiting for video generation to complete...")
            time.sleep(10)
            operation = client.operations.get(operation=operation)

        # When done, download the video
        generated_video = operation.response.generated_videos[0]
        video_file = generated_video.video  # this is the File object

        # Download via client.files.download(...)
        # Depending on the SDK version, download() may stream bytes or return content directly.
        downloaded = client.files.download(file=video_file)

        output_path = VIDEO_OUTPUT_DIR / f"{operation_id}.mp4"

        try:
            # If `downloaded` is a bytes-like object, write it directly.
            if isinstance(downloaded, (bytes, bytearray, memoryview)):
                with open(output_path, "wb") as f:
                    f.write(bytes(downloaded))
            else:
                with open(output_path, "wb") as f:
                    for chunk in downloaded:
                        if isinstance(chunk, int):
                            f.write(bytes([chunk]))
                        else:
                            f.write(bytes(chunk))
        except TypeError:
            # If `downloaded` is already raw bytes (or an unexpected bytes-like), write directly
            with open(output_path, "wb") as f:
                f.write(bytes(downloaded) if isinstance(downloaded, (bytearray, memoryview)) else downloaded)

        # Mark as completed
        job_statuses[operation_id]["status"] = "COMPLETED"
        job_statuses[operation_id]["file_path"] = str(output_path)
        print(f"[{operation_id}] Video saved to {output_path}")

    except Exception as e:
        print(f"operation result: {operation.response.rai_media_filtered_reasons if operation.response else 'No response'}")
        job_statuses[operation_id]["status"] = "ERROR"
        job_statuses[operation_id]["error"] = str(e)
        print(f"[{operation_id}] Error in background video generation: {e}")


def generate_video_from_image(image: bytes, content_type: str, duration: int) -> VideoGenerationStatus:
    operation = client.models.generate_videos(
        model="veo-2.0-generate-001",
        prompt=
            """Generate a subtle cinematic motion from this photo while strictly preserving the person’s identity.

DO NOT:
- Change facial structure or expressions unnaturally.
- Add or remove any people or objects.
- Modify the original artistic style or lighting drastically.

DO:
- Add gentle breathing.
- Add realistic blinking.
- Add minimal parallax to create depth.
- Slight ambient wind effect on hair or clothing (if plausible).
- Keep emotions and personality identical to the original photo.
- Fill in the black bar if exists and make the video full screen.""",
        image=Image(image_bytes=image, mime_type=content_type),
        config=GenerateVideosConfig(
            # resolution="720p",
            aspect_ratio="16:9",
            duration_seconds=duration,
            negative_prompt="Remove the black bars. Make sure the image is full screen without any black bars.",
            # generate_audio=False
        ),
    )

    # Safely extract operation name & id
    operation_name = getattr(operation, "name", None)
    if not operation_name:
        raise RuntimeError("generate_videos returned an operation with no name")
    operation_id = operation_name.rsplit("/", 1)[-1]

    # Store initial status
    job_statuses[operation_id] = {
        "status": "IN_PROGRESS",
        "file_path": None,
    }

    # Start background worker thread
    thread = threading.Thread(
        target=_poll_and_download_video,
        args=(operation, operation_id),
        daemon=True,
    )
    thread.start()

    # Return immediately
    return VideoGenerationStatus(status="IN_PROGRESS", operation_id=operation_id)

def check_for_video_completion(operation_id: str) -> VideoGenerationStatus:
    output_path = VIDEO_OUTPUT_DIR / f"{operation_id}.mp4"
    if output_path.exists():
        return VideoGenerationStatus(
            status="COMPLETED",
            operation_id=operation_id,
        )

    try:
        entry = job_statuses.get(operation_id)
        if entry is None:
            # Operation not tracked or missing; signal not found
            raise KeyError(f"Operation ID {operation_id} not found in job_statuses")
    
        operation = client.operations.get(operation=entry["operation"])
        if operation.done:
            # Video generation completed
            return VideoGenerationStatus(
                status="COMPLETED",
                operation_id=operation_id,
            )
        else:
            return VideoGenerationStatus(
                status="IN_PROGRESS",
                operation_id=operation_id,
            )
    except KeyError:
        raise RuntimeError(f"Operation ID {operation_id} not found in job_statuses")
    except Exception as e:
        raise RuntimeError(f"Error checking operation status: {str(e)}")
