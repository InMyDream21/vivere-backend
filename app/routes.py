from __future__ import annotations
from fastapi import APIRouter, HTTPException, UploadFile, File
from app.schemas import SuggestionRequest, SuggestionResponse, InitialQuestionResponse
from app.gemini import generate_suggestions, generate_suggestions_for_image
from app.utils import extract_json
from app.prompt import build_prompt

router = APIRouter()

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