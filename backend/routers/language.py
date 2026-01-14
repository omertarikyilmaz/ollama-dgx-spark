"""Language detection endpoint"""
from fastapi import APIRouter, HTTPException
from models import LanguageDetectRequest, LanguageDetectResponse
from core.config import LANG_MAP
import langid

router = APIRouter(tags=["Language"])


@router.post("/detect-language", response_model=LanguageDetectResponse)
async def detect_language(request: LanguageDetectRequest):
    """Detect the language of the provided text using local langid library"""
    try:
        iso_code, confidence = langid.classify(request.text)
        language_name = LANG_MAP.get(iso_code, iso_code.upper())

        return LanguageDetectResponse(
            language=iso_code,
            language_name=language_name,
            confidence=float(confidence) if confidence < 1 else 0.99
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
