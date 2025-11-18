from __future__ import annotations

import asyncio
import json
import queue
import os
import uuid
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor
import httpx
from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    File,
    WebSocket,
    WebSocketDisconnect,
    Response,
)
from app.schemas import (
    SuggestionRequest,
    SuggestionResponse,
    InitialQuestionResponse,
    VideoPromptResponse,
    VideoPromptTestResponse,
    VideoJobResponse,
    VideoStatusResponse,
    QueueStatusResponse,
    QueueTaskInfo,
    CancelTasksResponse,
    GenerationHistoryResponse,
    GenerationHistoryItem,
)
from app.gemini import (
    generate_suggestions,
    generate_suggestions_for_image,
    generate_video_prompt_from_image,
)
from app.utils import extract_json
from app.prompt import build_prompt
from app.speech_recognizer import (
    gcp_streaming_recognize,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    CHANNELS,
)
from app.comfyui_client import ComfyUIClient
from app.config import get_config

router = APIRouter()
executor = ThreadPoolExecutor()

# Singleton ComfyUI client instance
_comfyui_client: ComfyUIClient | None = None


def get_comfyui_client() -> ComfyUIClient:
    """Get or create ComfyUI client instance"""
    global _comfyui_client
    if _comfyui_client is None:
        _comfyui_client = ComfyUIClient()
        _comfyui_client.connect_websocket()
    return _comfyui_client


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
    # if len(transcript) < 20:
    #     raise HTTPException(status_code=400, detail="Transkrip terlalu pendek untuk analisis yang bermakna.")

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


@router.post("/generate_video", response_model=VideoJobResponse)
async def generate_video(image: UploadFile = File(...)):
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

    # Generate prompt from image using Gemini
    try:
        prompt = generate_video_prompt_from_image(content, image.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal menghasilkan prompt video: {str(e)}"
        )

    if not prompt:
        raise HTTPException(
            status_code=500, detail="Model tidak mengembalikan prompt apapun."
        )

    prompt = prompt.strip()

    # Generate video using ComfyUI
    try:
        client = get_comfyui_client()

        # Generate unique filename for uploaded image
        file_ext = Path(image.filename).suffix if image.filename else ".jpg"
        image_filename = f"{uuid.uuid4()}{file_ext}"

        # Queue video generation (runs in background, takes ~1 hour)
        prompt_id = await asyncio.get_event_loop().run_in_executor(
            executor, client.generate_video, content, image_filename, prompt
        )

        # Get initial status
        status_info = client.get_status(prompt_id)

        return VideoJobResponse(
            job_id=prompt_id,
            prompt=prompt,
            status=status_info.get("status", "queued"),
            progress=status_info.get("progress", 0),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal mengirim job ke ComfyUI: {str(e)}"
        )


@router.post("/generate_video/test_prompt", response_model=VideoPromptTestResponse)
async def test_video_prompt(image: UploadFile = File(...)):
    """
    Test endpoint to generate video prompt from image without running workflow.
    Useful for testing prompt generation without waiting for video generation.
    """
    # Validate image type
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

    # Generate prompt from image using Gemini
    try:
        prompt = generate_video_prompt_from_image(content, image.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal menghasilkan prompt video: {str(e)}"
        )

    if not prompt:
        raise HTTPException(
            status_code=500, detail="Model tidak mengembalikan prompt apapun."
        )

    prompt = prompt.strip()

    return VideoPromptTestResponse(prompt=prompt)


@router.get("/generate_video/{job_id}/status", response_model=VideoStatusResponse)
async def get_video_status(job_id: str):
    """Get status of video generation job"""
    try:
        client = get_comfyui_client()
        status_info = client.get_status(job_id)

        if status_info.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Job {job_id} tidak ditemukan")

        # If completed, provide download URL
        video_url = None
        if status_info.get("status") == "completed":
            video_url = f"/generate_video/{job_id}/download"

        return VideoStatusResponse(
            job_id=job_id,
            status=status_info.get("status", "unknown"),
            progress=status_info.get("progress", 0),
            video_url=video_url,
            error=status_info.get("error"),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal mendapatkan status job: {str(e)}"
        )


@router.get("/generate_video/{job_id}/download")
async def download_video(job_id: str):
    """Download the generated video"""
    try:
        client = get_comfyui_client()
        status_info = client.get_status(job_id)

        if status_info.get("status") == "not_found":
            raise HTTPException(status_code=404, detail=f"Job {job_id} tidak ditemukan")

        if status_info.get("status") != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Video belum selesai. Status: {status_info.get('status')}",
            )

        # Get video bytes
        video_bytes = await asyncio.get_event_loop().run_in_executor(
            executor, client.get_video_bytes, job_id
        )

        if not video_bytes:
            raise HTTPException(
                status_code=404,
                detail="Video tidak ditemukan atau gagal diambil dari ComfyUI",
            )

        # Determine filename
        video_filename = status_info.get("video_filename", f"{job_id}.mp4")
        if not video_filename.endswith((".mp4", ".webm", ".mov")):
            video_filename = f"{job_id}.mp4"

        # Build headers
        headers = {
            "Content-Disposition": f'attachment; filename="{video_filename}"',
            "Content-Length": str(len(video_bytes)),
        }

        # Add duration header if available
        duration_seconds = status_info.get("duration_seconds")
        if duration_seconds is not None:
            headers["X-Generation-Duration-Seconds"] = str(round(duration_seconds, 2))

        # Return video file
        return Response(
            content=video_bytes,
            media_type="video/mp4",
            headers=headers,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengunduh video: {str(e)}")


@router.websocket("/ws/video/{job_id}")
async def ws_video_status(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time video generation status updates"""
    await websocket.accept()

    try:
        client = get_comfyui_client()

        # Check if job exists
        initial_status = client.get_status(job_id)
        if initial_status.get("status") == "not_found":
            await websocket.send_text(
                json.dumps(
                    {"type": "error", "message": f"Job {job_id} tidak ditemukan"}
                )
            )
            await websocket.close()
            return

        # Send initial status
        await websocket.send_text(
            json.dumps(
                {
                    "type": "status",
                    "job_id": job_id,
                    "status": initial_status.get("status", "unknown"),
                    "progress": initial_status.get("progress", 0),
                    "video_url": (
                        f"/generate_video/{job_id}/download"
                        if initial_status.get("status") == "completed"
                        else None
                    ),
                }
            )
        )

        # Monitor for status changes
        last_status = initial_status.get("status")
        last_progress = initial_status.get("progress", 0)

        while True:
            await asyncio.sleep(1)  # Check every second

            current_status = client.get_status(job_id)
            current_status_value = current_status.get("status", "unknown")
            current_progress = current_status.get("progress", 0)

            # Send update if status or progress changed
            if current_status_value != last_status or current_progress != last_progress:

                video_url = None
                if current_status_value == "completed":
                    video_url = f"/generate_video/{job_id}/download"

                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "status",
                            "job_id": job_id,
                            "status": current_status_value,
                            "progress": current_progress,
                            "video_url": video_url,
                            "error": current_status.get("error"),
                        }
                    )
                )

                last_status = current_status_value
                last_progress = current_progress

                # Close connection if completed or error
                if current_status_value in ("completed", "error"):
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "done",
                                "job_id": job_id,
                                "status": current_status_value,
                            }
                        )
                    )
                    break

            # Check for client disconnect
            try:
                msg = await websocket.receive()
                if msg["type"] == "websocket.disconnect":
                    break
            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        print(f"WebSocket client disconnected for job {job_id}")
    except Exception as e:
        print(f"Error in video status WebSocket: {e}")
        try:
            await websocket.send_text(
                json.dumps({"type": "error", "message": str(e)})
            )
        except:
            pass
    finally:
            try:
                await websocket.close()
            except:
                pass


def _parse_queue_tasks(
    queue_list: list, client, default_status: str = "running"
) -> list[QueueTaskInfo]:
    """Parse ComfyUI queue list into QueueTaskInfo objects"""
    tasks = []
    for idx, task in enumerate(queue_list):
        if not isinstance(task, list) or len(task) == 0:
            continue

        prompt_id = str(task[0]) if task[0] else None
        if not prompt_id:
            continue

        # Get status info for this job
        status_info = client.get_status(prompt_id)
        video_url = None
        if status_info.get("status") == "completed":
            video_url = f"/generate_video/{prompt_id}/download"

        tasks.append(
            QueueTaskInfo(
                prompt_id=prompt_id,
                job_id=prompt_id,
                number=idx + 1,
                status=status_info.get("status", default_status),
                progress=status_info.get("progress", 0),
                node_progress=status_info.get("node_progress"),
                elapsed_time=status_info.get("elapsed_time"),
                duration_seconds=status_info.get("duration_seconds"),
                video_url=video_url,
                error=status_info.get("error"),
            )
        )
    return tasks


@router.get("/comfyui/queue", response_model=QueueStatusResponse)
async def get_comfyui_queue():
    """Get ComfyUI queue status - running and pending tasks"""
    try:
        client = get_comfyui_client()
        queue_data = client.get_queue()

        # ComfyUI returns queue in format:
        # {
        #   "queue_running": [[prompt_id, client_id, extra_data], ...],
        #   "queue_pending": [[prompt_id, client_id, extra_data], ...]
        # }
        queue_running = queue_data.get("queue_running", [])
        queue_pending = queue_data.get("queue_pending", [])

        running_tasks = (
            _parse_queue_tasks(queue_running, client, "running")
            if isinstance(queue_running, list)
            else []
        )
        pending_tasks = (
            _parse_queue_tasks(queue_pending, client, "queued")
            if isinstance(queue_pending, list)
            else []
        )

        return QueueStatusResponse(
            running=running_tasks,
            pending=pending_tasks,
            total_running=len(running_tasks),
            total_pending=len(pending_tasks),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal mengambil status queue ComfyUI: {str(e)}"
        )


@router.post("/comfyui/queue/cancel", response_model=CancelTasksResponse)
async def cancel_all_comfyui_tasks():
    """Cancel all running and pending tasks in ComfyUI queue"""
    try:
        client = get_comfyui_client()

        # First interrupt running task
        interrupted = client.interrupt()

        # Then clear pending queue
        cleared = client.clear_queue()

        if interrupted or cleared:
            return CancelTasksResponse(
                success=True,
                message="Berhasil membatalkan semua task ComfyUI",
                interrupted=interrupted,
                cleared=cleared,
            )
        else:
            return CancelTasksResponse(
                success=False,
                message="Gagal membatalkan task ComfyUI",
                interrupted=False,
                cleared=False,
            )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal membatalkan task ComfyUI: {str(e)}"
        )


@router.get("/generate_video/history", response_model=GenerationHistoryResponse)
async def get_generation_history():
    """Get all video generation history from ComfyUI"""
    try:
        client = get_comfyui_client()
        history_jobs = await asyncio.get_event_loop().run_in_executor(
            executor, client.get_all_generation_history
        )

        # Convert to response format
        jobs = []
        for job in history_jobs:
            video_url = None
            if job.get("status") == "completed" and job.get("video_filename"):
                job_id = job.get("job_id")
                video_url = f"/generate_video/{job_id}/download"

            jobs.append(
                GenerationHistoryItem(
                    job_id=job.get("job_id"),
                    status=job.get("status", "unknown"),
                    progress=job.get("progress", 0),
                    duration_seconds=job.get("duration_seconds"),
                    video_filename=job.get("video_filename"),
                    video_url=video_url,
                    error=job.get("error"),
                )
            )

        return GenerationHistoryResponse(total=len(jobs), jobs=jobs)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gagal mengambil history generasi video: {str(e)}",
        )


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
