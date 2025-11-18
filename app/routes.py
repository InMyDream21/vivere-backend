from __future__ import annotations

import asyncio
import json
import queue
import os
import uuid
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor
from fastapi.responses import FileResponse
import httpx
from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    File,
    WebSocket,
    WebSocketDisconnect,
    Form
)
from app.schemas import (
    SuggestionRequest,
    SuggestionResponse,
    InitialQuestionResponse,
    VideoGenerationResponse,
    VideoGenerationRequest,
    VideoGenerationStatus,
    # VideoPromptResponse,
    # VideoPromptTestResponse,
    # VideoJobResponse,
    # VideoStatusResponse,
    # QueueStatusResponse,
    # QueueTaskInfo,
    # CancelTasksResponse,
    # GenerationHistoryResponse,
    # GenerationHistoryItem,
)
from app.gemini import (
    generate_suggestions,
    generate_suggestions_for_image,
    generate_video_prompt_from_image,
    generate_video_from_image,
    check_for_video_completion,
)
from app.utils import extract_json
from app.prompt import build_prompt
from app.speech_recognizer import (
    gcp_streaming_recognize,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    CHANNELS,
)
from app.config import get_config

router = APIRouter()
executor = ThreadPoolExecutor()

@router.get("/health")
def health_check():
    return {"status": "healthy"}


@router.get("/metrics/cpu")
async def get_cpu_metrics():
    """Get CPU metrics from Glances"""
    config = get_config()
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{config.GLANCES_URL}/cpu", timeout=5.0)
            if r.status_code != 200:
                raise HTTPException(
                    status_code=502, detail="Glances CPU fetch failed"
                )
            return r.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="Glances API timeout"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503, detail="Glances service unavailable"
        )


@router.get("/metrics/mem")
async def get_mem_metrics():
    """Get memory metrics from Glances"""
    config = get_config()
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{config.GLANCES_URL}/mem", timeout=5.0)
            if r.status_code != 200:
                raise HTTPException(
                    status_code=502, detail="Glances memory fetch failed"
                )
            return r.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="Glances API timeout"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503, detail="Glances service unavailable"
        )


@router.get("/metrics/load")
async def get_load_metrics():
    """Get system load metrics from Glances"""
    config = get_config()
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{config.GLANCES_URL}/load", timeout=5.0)
            if r.status_code != 200:
                raise HTTPException(
                    status_code=502, detail="Glances load fetch failed"
                )
            return r.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="Glances API timeout"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503, detail="Glances service unavailable"
        )


@router.get("/metrics/all")
async def get_all_metrics():
    """Get all system metrics from Glances"""
    config = get_config()
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{config.GLANCES_URL}/all", timeout=5.0)
            if r.status_code != 200:
                raise HTTPException(
                    status_code=502, detail="Glances ALL fetch failed"
                )
            return r.json()
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504, detail="Glances API timeout"
        )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503, detail="Glances service unavailable"
        )


@router.post("/suggestions", response_model=SuggestionResponse)
async def get_suggestions(request: SuggestionRequest):
    transcript = (request.transcript or "").strip()

    max_suggestions = 3
    prompt = build_prompt(
        transcription=transcript,
        locale="id-ID",
        max_suggestions=max_suggestions,
    )

    try:
        text = generate_suggestions(prompt)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal menghasilkan saran: {str(e)}"
        )

    if not text or text == "<no_suggestion>":
        raise HTTPException(
            status_code=500, detail="Model tidak mengembalikan saran apapun."
        )

    try:
        data = extract_json(text)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal mengurai respons model: {str(e)}"
        )

    raw_suggestions = data.get("suggestions", [])
    suggestions = []
    for s in raw_suggestions[:max_suggestions]:
        suggestions.append(s.strip())

        if not suggestions:
            return HTTPException(
                status_code=500,
                detail="Tidak ada saran valid yang ditemukan dalam respons model.",
            )

    return SuggestionResponse(
        suggestions=suggestions,
    )


@router.post("/initial-questions", response_model=InitialQuestionResponse)
async def get_initial_questions(image: UploadFile = File(...)):
    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    }
    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {image.content_type}. Allowed: {', '.join(sorted(allowed_types))}",
        )

    content = await image.read()
    if not content:
        raise HTTPException(
            status_code=400, detail="File gambar kosong atau gagal dibaca."
        )

    try:
        text = generate_suggestions_for_image(content, image.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal menghasilkan pertanyaan awal: {str(e)}"
        )

    if not text or text == "<no_suggestion>":
        raise HTTPException(
            status_code=500, detail="Model tidak mengembalikan saran apapun."
        )

    try:
        data = extract_json(text)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal mengurai respons model: {str(e)}"
        )

    raw_questions = data.get("question", "")

    return InitialQuestionResponse(
        question=raw_questions.strip(),
    )

@router.post("/video/generate", response_model=VideoGenerationStatus)
async def generate_video(
    image: UploadFile = File(...),
    duration: int = Form(8)
):
    allowed_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        "image/heif",
    }
    if image.content_type not in allowed_types:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported media type: {image.content_type}. Allowed: {', '.join(sorted(allowed_types))}",
        )

    content = await image.read()
    if not content:
        raise HTTPException(
            status_code=400, detail="File gambar kosong atau gagal dibaca."
        )
    
    # Validate and sanitize requested video duration
    allowed_durations = {4, 6, 8}
    if duration not in allowed_durations:
        raise HTTPException(
            status_code=422,
            detail=f"Durasi tidak valid. Hanya nilai {sorted(allowed_durations)} yang didukung.",
        )

    video_duration = duration

    # Generate prompt from image using Gemini
    # try:
    #     prompt = generate_video_prompt_from_image(content, image.content_type)
    # except Exception as e:
    #     raise HTTPException(
    #         status_code=500, detail=f"Gagal menghasilkan prompt video: {str(e)}"
    #     )

    # if not prompt:
    #     raise HTTPException(
    #         status_code=500, detail="Model tidak mengembalikan prompt apapun."
    #     )

    # prompt = prompt.strip()
    # print(f"Generated video prompt: {prompt}")

    try:
        response = generate_video_from_image(content, image.content_type, video_duration)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal memulai generasi video: {str(e)}"
        )
    return response

@router.get("/video/status/{operation_id}", response_model=VideoGenerationStatus)
def get_video_status(operation_id: str):
    """
    Checks the status of a video generation job and returns the video URL if complete.
    """

    try:
        response = check_for_video_completion(operation_id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal memeriksa status video: {str(e)}"
        )
    return response

@router.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    await websocket.accept()

    audio_q = queue.Queue()
    result_q = queue.Queue()

    loop = asyncio.get_event_loop()
    # Start GCP recognizer in a thread
    recog_future = loop.run_in_executor(
        executor, gcp_streaming_recognize, audio_q, result_q
    )

    # Task: forward recognizer outputs to the client
    async def forward_results():
        try:
            while True:
                # Block on results coming from recognizer thread
                transcript, is_final = await loop.run_in_executor(None, result_q.get)
                if transcript is None:  # Sentinel value from recognizer thread
                    break
                try:
                    payload = {
                        "type": "transcript",
                        "final": is_final,
                        "text": transcript,
                    }
                    await websocket.send_text(json.dumps(payload))
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    print(f"Error sending transcript: {e}")
                    break
        except asyncio.CancelledError:
            pass  # Clean shutdown on task cancellation

    forward_task = asyncio.create_task(forward_results())

    try:
        while True:
            msg = await websocket.receive()
            if msg["type"] == "websocket.disconnect":
                break

            if msg.get("bytes") is not None:
                # normal audio frame
                audio_q.put(msg["bytes"])

            elif msg.get("text") is not None:
                data = json.loads(msg["text"])
                if data.get("type") == "stop":
                    audio_q.put(None)
    except WebSocketDisconnect:
        print("WebSocket client disconnected.")
    except Exception as e:
        print(f"Error in main receive loop: {e}")
    finally:
        try:
            audio_q.put(None)
            await recog_future
        except Exception as e:
            print(f"Error during recognizer shutdown: {e}")

        try:
            await forward_task
        except Exception as e:
            print(f"Error waiting for forward task: {e}")

VIDEO_OUTPUT_DIR = Path("generated_videos")
@router.get("/video/file/{operation_id}")
def download_video(operation_id: str):
    """
    Return the generated video file for a given operation_id.
    """
    file_path = VIDEO_OUTPUT_DIR / f"{operation_id}.mp4"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(
        path=file_path,
        media_type="video/mp4",
        filename=f"{operation_id}.mp4",
    )
