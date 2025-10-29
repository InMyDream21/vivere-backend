from __future__ import annotations
from fastapi import APIRouter, HTTPException
from app.schemas import SuggestionRequest, SuggestionResponse
from app.gemini import generate_suggestions
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
    
    print("Final suggestions:", suggestions)
    return SuggestionResponse(
        suggestions=suggestions,
    )