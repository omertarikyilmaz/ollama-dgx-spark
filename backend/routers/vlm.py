"""
Vision Language Model (VLM) endpoints for image and video analysis
Optimized for Qwen2.5-VL and Qwen3-VL on NVIDIA DGX Spark
"""
import os
import base64
import subprocess
import tempfile
import time
import json
import re
import httpx
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from models import (
    VLMImageAnalysisResponse, VLMVideoAnalysisResponse,
    DetectedPerson, DetectedLogo, DetectedText, VideoFrame,
    BoundingBox, VLMModelInfo
)

router = APIRouter(tags=["VLM"])

# Ollama base URL
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

# Available VLM models
VLM_MODELS = [
    VLMModelInfo(
        name="qwen3-vl:4b",
        size="3.1GB",
        description="Qwen3-VL 4B - En hizli, 32 dil OCR, Turkce destekli",
        supports_video=True,
        recommended=True
    ),
    VLMModelInfo(
        name="qwen3-vl:8b",
        size="6GB",
        description="Qwen3-VL 8B - Hizli + Kaliteli, 32 dil OCR",
        supports_video=True
    ),
    VLMModelInfo(
        name="blaifa/InternVL3_5:4B",
        size="3.4GB",
        description="InternVL3.5 4B - Yuksek dogruluk, Turkce test edildi",
        supports_video=True
    ),
    VLMModelInfo(
        name="qwen3-vl:32b",
        size="21GB",
        description="Qwen3-VL 32B - En kaliteli, 256K context",
        supports_video=True
    ),
    VLMModelInfo(
        name="qwen2.5vl:32b",
        size="21GB",
        description="Qwen2.5-VL 32B - Stabil, 29 dil OCR",
        supports_video=True
    ),
]

# System prompts for analysis
PERSON_LOGO_PROMPT = """Sen bir görüntü analiz uzmanısın. Bu görüntüyü analiz et ve şunları bul:

1. **Kişiler**: Görüntüdeki kişileri tespit et. Eğer isim etiketi, alt yazı veya metin ile isimleri belirtilmişse oku.
2. **Logolar**: Şirket veya kurum logolarını tespit et ve hangi şirkete ait olduğunu belirle.
3. **Metin**: Görüntüdeki önemli metinleri (başlıklar, alt yazılar, tabelalar) oku.

JSON formatında yanıt ver:
```json
{
    "persons": [
        {"name": "Kişi Adı", "title": "Unvan (varsa)", "confidence": 0.95}
    ],
    "logos": [
        {"company": "Şirket Adı", "confidence": 0.9}
    ],
    "texts": [
        {"text": "Okunan metin", "language": "tr"}
    ],
    "scene_description": "Sahnenin kısa açıklaması"
}
```

Önemli kurallar:
- Sadece görüntüde gerçekten gördüklerini raporla
- Eğer isim okunamıyorsa "Bilinmeyen Kişi" yaz
- Güven skorları 0-1 arası olmalı
- Türkçe karakterleri doğru kullan"""


def encode_image_to_base64(image_bytes: bytes) -> str:
    """Encode image bytes to base64 string"""
    return base64.b64encode(image_bytes).decode('utf-8')


def extract_video_frames(video_path: str, interval: float, max_frames: int) -> list:
    """
    Extract frames from video at specified intervals using FFmpeg.
    Returns list of (timestamp, frame_path) tuples.
    """
    # Get video duration
    duration_cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    result = subprocess.run(duration_cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip()) if result.stdout.strip() else 0.0

    frames = []
    temp_dir = tempfile.mkdtemp()

    # Calculate timestamps
    timestamps = []
    current = 0.0
    while current < duration and len(timestamps) < max_frames:
        timestamps.append(current)
        current += interval

    # Extract frames
    for i, ts in enumerate(timestamps):
        output_path = os.path.join(temp_dir, f"frame_{i:04d}.jpg")
        extract_cmd = [
            'ffmpeg', '-y', '-ss', str(ts),
            '-i', video_path,
            '-vframes', '1',
            '-q:v', '2',
            output_path
        ]
        subprocess.run(extract_cmd, capture_output=True)

        if os.path.exists(output_path):
            frames.append((ts, output_path))

    return frames, duration, temp_dir


def format_timestamp(seconds: float) -> str:
    """Format seconds to HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_vlm_response(response_text: str) -> dict:
    """Parse VLM response and extract structured data"""
    # Try to find JSON in the response
    json_match = re.search(r'\{[\s\S]*\}', response_text)

    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback: return raw response
    return {
        "persons": [],
        "logos": [],
        "texts": [],
        "scene_description": response_text[:500]
    }


# Cache for verified models - avoid repeated /api/tags calls
_verified_models = set()


async def ensure_model_available(model: str) -> bool:
    """Check if model exists (with cache), pull if not. Returns True if ready."""
    global _verified_models

    # Already verified this session
    if model in _verified_models:
        return True

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                for m in models:
                    name = m.get("name", "")
                    # Check exact or partial match
                    if model == name or model in name or name.startswith(model.split(":")[0]):
                        _verified_models.add(model)
                        print(f"Model '{model}' hazir.")
                        return True
        except Exception as e:
            print(f"Model kontrol hatasi: {e}")
            # Continue anyway - let Ollama handle it
            return True

    # Model not found, pull it
    print(f"Model '{model}' bulunamadi, indiriliyor...")
    async with httpx.AsyncClient(timeout=1800.0) as client:
        try:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/pull",
                json={"name": model, "stream": False}
            )
            if response.status_code == 200:
                _verified_models.add(model)
                print(f"Model '{model}' basariyla indirildi!")
                return True
        except Exception as e:
            print(f"Model indirme hatasi: {e}")

    return False


async def call_vlm(model: str, image_base64: str, prompt: str) -> dict:
    """Call Ollama VLM API with image."""

    # One-time check per model per session
    await ensure_model_available(model)

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_ctx": 8192
                }
            }
        )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"Ollama error: {response.text}")

        return response.json()


@router.get("/vlm-models")
async def list_vlm_models():
    """List available VLM models"""
    return {
        "models": [m.model_dump() for m in VLM_MODELS],
        "recommended": "qwen2.5vl:32b"
    }


@router.get("/vlm-health")
async def vlm_health():
    """Check VLM service health and available models"""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")

            if response.status_code == 200:
                data = response.json()
                models = data.get("models", [])

                # Check which VLM models are available
                vlm_available = []
                for model in models:
                    name = model.get("name", "")
                    if "qwen" in name.lower() and "vl" in name.lower():
                        vlm_available.append(name)

                return {
                    "status": "ready",
                    "ollama_connected": True,
                    "vlm_models_available": vlm_available,
                    "recommended_model": vlm_available[0] if vlm_available else "qwen2.5vl:32b (pull gerekli)"
                }
            else:
                return {
                    "status": "error",
                    "ollama_connected": False,
                    "message": "Ollama connection failed"
                }
    except Exception as e:
        return {
            "status": "error",
            "ollama_connected": False,
            "message": str(e)
        }


@router.post("/analyze-image", response_model=VLMImageAnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    model: str = Form("qwen3-vl:4b"),
    analyze_persons: bool = Form(True),
    analyze_logos: bool = Form(True),
    analyze_text: bool = Form(True),
    custom_prompt: Optional[str] = Form(None)
):
    """
    Analyze image using Vision Language Model.
    Detects persons (with names), logos, and text.
    """
    start_time = time.time()

    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        return VLMImageAnalysisResponse(
            success=False,
            error=f"Desteklenmeyen dosya türü: {file.content_type}. Sadece görsel dosyaları desteklenir."
        )

    try:
        # Read and encode image
        content = await file.read()
        image_base64 = encode_image_to_base64(content)

        # Build prompt
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompt = PERSON_LOGO_PROMPT

        # Call VLM
        result = await call_vlm(model, image_base64, prompt)

        raw_response = result.get("response", "")
        parsed = parse_vlm_response(raw_response)

        # Build response
        persons = []
        for p in parsed.get("persons", []):
            persons.append(DetectedPerson(
                name=p.get("name", "Bilinmeyen"),
                title=p.get("title"),
                confidence=float(p.get("confidence", 0.8))
            ))

        logos = []
        for l in parsed.get("logos", []):
            logos.append(DetectedLogo(
                company=l.get("company", "Bilinmeyen"),
                confidence=float(l.get("confidence", 0.8))
            ))

        texts = []
        for t in parsed.get("texts", []):
            texts.append(DetectedText(
                text=t.get("text", ""),
                language=t.get("language", "tr")
            ))

        processing_time = (time.time() - start_time) * 1000

        return VLMImageAnalysisResponse(
            success=True,
            persons=persons,
            logos=logos,
            texts=texts,
            scene_description=parsed.get("scene_description", ""),
            raw_response=raw_response,
            processing_time_ms=processing_time,
            model_used=model
        )

    except Exception as e:
        import traceback
        return VLMImageAnalysisResponse(
            success=False,
            error=str(e) + "\n" + traceback.format_exc(),
            processing_time_ms=(time.time() - start_time) * 1000
        )


@router.post("/analyze-video", response_model=VLMVideoAnalysisResponse)
async def analyze_video(
    file: UploadFile = File(...),
    model: str = Form("qwen3-vl:4b"),
    frame_interval: float = Form(5.0),
    max_frames: int = Form(50),
    analyze_persons: bool = Form(True),
    analyze_logos: bool = Form(True)
):
    """
    Analyze video using Vision Language Model.
    Extracts frames at intervals and detects persons/logos with timestamps.
    """
    start_time = time.time()

    # Validate file type
    valid_types = ['video/mp4', 'video/webm', 'video/x-msvideo', 'video/quicktime', 'video/x-matroska']
    if not file.content_type or not any(file.content_type.startswith(t) for t in valid_types):
        return VLMVideoAnalysisResponse(
            success=False,
            error=f"Desteklenmeyen dosya türü: {file.content_type}. MP4, WEBM, AVI, MOV, MKV desteklenir."
        )

    tmp_video_path = None
    temp_dir = None

    try:
        # Save video to temp file
        content = await file.read()
        suffix = os.path.splitext(file.filename)[1] if file.filename else '.mp4'

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_video_path = tmp.name

        # Extract frames
        frames_data, duration, temp_dir = extract_video_frames(
            tmp_video_path, frame_interval, max_frames
        )

        if not frames_data:
            return VLMVideoAnalysisResponse(
                success=False,
                error="Video kareleri çıkarılamadı. FFmpeg kurulu olduğundan emin olun."
            )

        # Analyze each frame
        video_frames = []
        all_persons = set()
        all_logos = set()

        for timestamp, frame_path in frames_data:
            with open(frame_path, 'rb') as f:
                frame_bytes = f.read()

            frame_base64 = encode_image_to_base64(frame_bytes)

            # Call VLM for this frame
            result = await call_vlm(model, frame_base64, PERSON_LOGO_PROMPT)
            parsed = parse_vlm_response(result.get("response", ""))

            # Extract persons and logos
            frame_persons = []
            for p in parsed.get("persons", []):
                person = DetectedPerson(
                    name=p.get("name", "Bilinmeyen"),
                    title=p.get("title"),
                    confidence=float(p.get("confidence", 0.8))
                )
                frame_persons.append(person)
                all_persons.add(person.name)

            frame_logos = []
            for l in parsed.get("logos", []):
                logo = DetectedLogo(
                    company=l.get("company", "Bilinmeyen"),
                    confidence=float(l.get("confidence", 0.8))
                )
                frame_logos.append(logo)
                all_logos.add(logo.company)

            video_frames.append(VideoFrame(
                timestamp=timestamp,
                timestamp_formatted=format_timestamp(timestamp),
                persons=frame_persons,
                logos=frame_logos,
                scene_description=parsed.get("scene_description", "")
            ))

        processing_time = (time.time() - start_time) * 1000

        return VLMVideoAnalysisResponse(
            success=True,
            frames=video_frames,
            unique_persons=sorted(list(all_persons)),
            unique_logos=sorted(list(all_logos)),
            video_duration=duration,
            frames_analyzed=len(video_frames),
            processing_time_ms=processing_time,
            model_used=model
        )

    except Exception as e:
        import traceback
        return VLMVideoAnalysisResponse(
            success=False,
            error=str(e) + "\n" + traceback.format_exc(),
            processing_time_ms=(time.time() - start_time) * 1000
        )

    finally:
        # Cleanup
        if tmp_video_path and os.path.exists(tmp_video_path):
            os.unlink(tmp_video_path)

        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)


@router.post("/vlm-chat")
async def vlm_chat(
    file: UploadFile = File(...),
    message: str = Form(...),
    model: str = Form("qwen3-vl:4b")
):
    """
    Chat with VLM about an image. Ask any question about the image content.
    """
    start_time = time.time()

    if not file.content_type or not file.content_type.startswith('image/'):
        return {
            "success": False,
            "error": "Sadece görsel dosyaları desteklenir."
        }

    try:
        content = await file.read()
        image_base64 = encode_image_to_base64(content)

        # Add Turkish context to the prompt
        prompt = f"""Türkçe yanıt ver. {message}"""

        result = await call_vlm(model, image_base64, prompt)

        return {
            "success": True,
            "response": result.get("response", ""),
            "processing_time_ms": (time.time() - start_time) * 1000,
            "model_used": model
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "processing_time_ms": (time.time() - start_time) * 1000
        }
