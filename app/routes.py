from __future__ import annotations

import asyncio
import json
import queue

from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, HTTPException, UploadFile, File, WebSocket, WebSocketDisconnect
from app.schemas import SuggestionRequest, SuggestionResponse, InitialQuestionResponse
from app.gemini import generate_suggestions, generate_suggestions_for_image
from app.utils import extract_json
from app.prompt import build_prompt
from app.speech_recognizer import gcp_streaming_recognize, SAMPLE_RATE, SAMPLE_WIDTH, CHANNELS

router = APIRouter()
executor = ThreadPoolExecutor()

@router.get("/health")
def health_check():
    return {"status": "healthy"}

@router.post("/suggestions", response_model=SuggestionResponse)
async def get_suggestions(request: SuggestionRequest):
    transcript = (request.transcript or "").strip()
    if len(transcript) < 20:
        raise HTTPException(status_code=400, detail="Transkrip terlalu pendek untuk analisis yang bermakna.")

    max_suggestions = 4
    prompt = build_prompt(
        transcription=transcript,
        locale="id-ID",
        max_suggestions=max_suggestions,
    )

    try:
        text = generate_suggestions(prompt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menghasilkan saran: {str(e)}")
    
    if not text or text == "<no_suggestion>":
        raise HTTPException(status_code=500, detail="Model tidak mengembalikan saran apapun.")
    
    try:
        data = extract_json(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengurai respons model: {str(e)}")
    
    raw_suggestions = data.get("suggestions", [])
    suggestions = []
    for s in raw_suggestions[:max_suggestions]:
        suggestions.append(s.strip())

        if not suggestions:
            return HTTPException(status_code=500, detail="Tidak ada saran valid yang ditemukan dalam respons model.")
    
    return SuggestionResponse(
        suggestions=suggestions,
    )

@router.post("/initial-questions", response_model=InitialQuestionResponse)
async def get_initial_questions(image: UploadFile = File(...)):
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}
    if image.content_type not in allowed_types:
        raise HTTPException(status_code=415, detail=f"Unsupported media type: {image.content_type}. Allowed: {', '.join(sorted(allowed_types))}")
    
    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail="File gambar kosong atau gagal dibaca.")
    
    try:
        text = generate_suggestions_for_image(content, image.content_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal menghasilkan pertanyaan awal: {str(e)}")
    
    if not text or text == "<no_suggestion>":
        raise HTTPException(status_code=500, detail="Model tidak mengembalikan saran apapun.")

    try:
        data = extract_json(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengurai respons model: {str(e)}")

    raw_questions = data.get("question", '')

    return InitialQuestionResponse(
        question=raw_questions.strip(),
    )

@router.websocket("/ws/audio")
async def ws_audio(websocket: WebSocket):
    await websocket.accept()

    audio_q = queue.Queue()
    result_q = queue.Queue()

    loop = asyncio.get_event_loop()
    # Start GCP recognizer in a thread
    recog_future = loop.run_in_executor(executor, gcp_streaming_recognize, audio_q, result_q)

    # Task: forward recognizer outputs to the client
    async def forward_results():
        try:
            while True:
                # Block on results coming from recognizer thread
                transcript, is_final = await loop.run_in_executor(None, result_q.get)
                if transcript is None:  # Sentinel value from recognizer thread
                    break
                try:
                    payload = {"type": "transcript", "final": is_final, "text": transcript}
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
