"""
Vision Language Model (VLM) endpoints for image and video analysis
Optimized for Qwen3-VL on ASUS Ascent GX10 (Grace Blackwell 128GB)
"""
import os
import asyncio
import base64
import subprocess
import tempfile
import time
import json
import re
import httpx
import logging
from datetime import datetime
from typing import Optional, List, Tuple
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VLM")

def log_info(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[VLM {timestamp}] ℹ️  {msg}", flush=True)

def log_success(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[VLM {timestamp}] ✅ {msg}", flush=True)

def log_warning(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[VLM {timestamp}] ⚠️  {msg}", flush=True)

def log_error(msg):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[VLM {timestamp}] ❌ {msg}", flush=True)

def log_progress(current, total, msg=""):
    timestamp = datetime.now().strftime("%H:%M:%S")
    pct = int((current / total) * 100) if total > 0 else 0
    bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
    print(f"[VLM {timestamp}] [{bar}] {pct}% - {msg}", flush=True)

from models import (
    VLMImageAnalysisResponse, VLMVideoAnalysisResponse,
    DetectedPerson, DetectedLogo, DetectedText, VideoFrame,
    BoundingBox, VLMModelInfo
)

router = APIRouter(tags=["VLM"])

# Ollama base URL
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

# GX10 128GB MAXIMUM PARALLEL - 32 concurrent requests
PARALLEL_BATCH_SIZE = int(os.getenv("VLM_BATCH_SIZE", "32"))
DEFAULT_VLM_MODEL = os.getenv("VLM_MODEL", "qwen2.5vl:32b")

# Available VLM models - All Qwen VL models
VLM_MODELS = [
    # Qwen 2.5 VL Series
    VLMModelInfo(
        name="qwen2.5vl:32b",
        size="21GB",
        description="Qwen2.5-VL 32B - Stabil, 29 dil OCR, GX10 optimize",
        supports_video=True,
        recommended=True
    ),
    VLMModelInfo(
        name="qwen2.5vl:72b",
        size="47GB",
        description="Qwen2.5-VL 72B - En buyuk, maksimum kalite",
        supports_video=True
    ),
    VLMModelInfo(
        name="qwen2.5vl:7b",
        size="5GB",
        description="Qwen2.5-VL 7B - Hizli, dengeli",
        supports_video=True
    ),
    VLMModelInfo(
        name="qwen2.5vl:3b",
        size="2GB",
        description="Qwen2.5-VL 3B - Cok hizli",
        supports_video=True
    ),
    # Qwen 3 VL Series
    VLMModelInfo(
        name="qwen3-vl:32b",
        size="21GB",
        description="Qwen3-VL 32B - Yeni nesil, 256K context",
        supports_video=True
    ),
    VLMModelInfo(
        name="qwen3-vl:8b",
        size="6GB",
        description="Qwen3-VL 8B - Hizli + Kaliteli",
        supports_video=True
    ),
    VLMModelInfo(
        name="qwen3-vl:4b",
        size="3.1GB",
        description="Qwen3-VL 4B - En Hizli",
        supports_video=True
    ),
]

# System prompts for analysis
PERSON_LOGO_PROMPT = """Bu bir Türk haber kanalı görüntüsü. Analiz et ve JSON döndür.

GÖREVLER:
1. KİŞİLER: Ekrandaki tüm kişileri bul. Alt yazıda (lower third/chyron) isim varsa oku ve eşleştir.
2. LOGOLAR: Kanal logosu ve diğer şirket/kurum logolarını tespit et.
3. METİNLER: Haber başlığı, alt yazılar, ekrandaki tüm Türkçe metinleri oku.

JSON FORMAT:
{"persons":[{"name":"Ahmet Yılmaz","title":"Ekonomist"}],"logos":[{"company":"TRT"},{"company":"CNN Türk"}],"texts":["Haber başlığı buraya"],"scene":"Stüdyoda sunucu konuşuyor"}

KURALLAR:
- İsim okunamıyorsa "Bilinmeyen Kişi 1", "Bilinmeyen Kişi 2" yaz
- Logo görüyorsan mutlaka ekle
- Tüm metinleri Türkçe doğru oku
- Boş array kullanma, tespit yoksa o alanı koy ama boş bırak"""


def encode_image_to_base64(image_bytes: bytes) -> str:
    """Encode image bytes to base64 string"""
    return base64.b64encode(image_bytes).decode('utf-8')


def extract_video_frames(video_path: str, interval: float, max_frames: int) -> list:
    """
    Extract frames from video at specified intervals using FFmpeg.
    Returns list of (timestamp, frame_path) tuples.
    """
    log_info("FFmpeg ile video bilgisi alınıyor...")

    # Get video duration
    duration_cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    result = subprocess.run(duration_cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip()) if result.stdout.strip() else 0.0

    log_info(f"Video süresi: {duration:.1f} saniye")

    frames = []
    temp_dir = tempfile.mkdtemp()

    # Calculate timestamps
    timestamps = []
    current = 0.0
    while current < duration and len(timestamps) < max_frames:
        timestamps.append(current)
        current += interval

    log_info(f"Çıkarılacak kare sayısı: {len(timestamps)}")
    log_info(f"Kare aralığı: her {interval} saniyede bir")

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

        # Progress log every 10 frames
        if (i + 1) % 10 == 0 or i == len(timestamps) - 1:
            log_progress(i + 1, len(timestamps), f"Kare çıkarma: {i + 1}/{len(timestamps)}")

    log_success(f"Toplam {len(frames)} kare başarıyla çıkarıldı")
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
            data = json.loads(json_match.group())
            # Normalize field names (scene vs scene_description)
            if "scene" in data and "scene_description" not in data:
                data["scene_description"] = data["scene"]
            # Add default confidence if missing
            for p in data.get("persons", []):
                if "confidence" not in p:
                    p["confidence"] = 0.9
            for l in data.get("logos", []):
                if "confidence" not in l:
                    l["confidence"] = 0.9
            return data
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
        log_info(f"Model '{model}' zaten doğrulandı (cache)")
        return True

    log_info(f"Model kontrol ediliyor: {model}")

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                log_info(f"Mevcut modeller: {', '.join(model_names) if model_names else 'yok'}")

                for m in models:
                    name = m.get("name", "")
                    # Check exact or partial match
                    if model == name or model in name or name.startswith(model.split(":")[0]):
                        _verified_models.add(model)
                        size = m.get("size", 0)
                        size_gb = size / (1024**3) if size else 0
                        log_success(f"Model '{model}' hazır ({size_gb:.1f} GB)")
                        return True
        except Exception as e:
            log_warning(f"Model kontrol hatası: {e}")
            # Continue anyway - let Ollama handle it
            return True

    # Model not found, pull it
    log_warning(f"Model '{model}' bulunamadı, indirme başlatılıyor...")
    log_info("Bu işlem model boyutuna göre birkaç dakika sürebilir...")

    async with httpx.AsyncClient(timeout=1800.0) as client:
        try:
            # Use streaming to show download progress
            async with client.stream(
                "POST",
                f"{OLLAMA_BASE_URL}/api/pull",
                json={"name": model, "stream": True},
                timeout=1800.0
            ) as response:
                last_status = ""
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            status = data.get("status", "")

                            if "completed" in data and "total" in data:
                                completed = data["completed"]
                                total = data["total"]
                                log_progress(completed, total, status)
                            elif status != last_status:
                                log_info(f"İndirme durumu: {status}")
                                last_status = status

                        except json.JSONDecodeError:
                            pass

            _verified_models.add(model)
            log_success(f"Model '{model}' başarıyla indirildi!")
            return True
        except Exception as e:
            log_error(f"Model indirme hatası: {e}")

    return False


async def call_vlm(model: str, image_base64: str, prompt: str, frame_info: str = "") -> dict:
    """Call Ollama VLM API with image."""

    # One-time check per model per session
    await ensure_model_available(model)

    frame_prefix = f"[{frame_info}] " if frame_info else ""
    log_info(f"{frame_prefix}VLM çağrısı başlatılıyor: {model}")

    call_start = time.time()

    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "images": [image_base64],
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_ctx": 4096,
                    "num_predict": 256,  # Kısa yanıt = hızlı
                }
            }
        )

        call_duration = time.time() - call_start

        if response.status_code != 200:
            log_error(f"{frame_prefix}Ollama hatası: {response.text}")
            raise HTTPException(status_code=response.status_code, detail=f"Ollama error: {response.text}")

        result = response.json()

        # Log performance metrics
        eval_count = result.get("eval_count", 0)
        eval_duration = result.get("eval_duration", 0) / 1e9 if result.get("eval_duration") else 0
        tokens_per_sec = eval_count / eval_duration if eval_duration > 0 else 0

        log_success(f"{frame_prefix}VLM yanıtı alındı: {call_duration:.1f}s, {eval_count} token, {tokens_per_sec:.1f} tok/s")

        return result


@router.get("/vlm-models")
async def list_vlm_models():
    """List available VLM models"""
    log_info("VLM model listesi istendi")
    return {
        "models": [m.model_dump() for m in VLM_MODELS],
        "recommended": "qwen3-vl:4b"
    }


@router.get("/vlm-health")
async def vlm_health():
    """Check VLM service health and available models"""
    log_info("VLM sağlık kontrolü başlatıldı")
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

                log_success(f"Ollama bağlantısı başarılı. {len(vlm_available)} VLM modeli mevcut")
                return {
                    "status": "ready",
                    "ollama_connected": True,
                    "vlm_models_available": vlm_available,
                    "recommended_model": vlm_available[0] if vlm_available else "qwen3-vl:4b (pull gerekli)"
                }
            else:
                log_error(f"Ollama bağlantı hatası: {response.status_code}")
                return {
                    "status": "error",
                    "ollama_connected": False,
                    "message": "Ollama connection failed"
                }
    except Exception as e:
        log_error(f"Sağlık kontrolü hatası: {str(e)}")
        return {
            "status": "error",
            "ollama_connected": False,
            "message": str(e)
        }


@router.post("/analyze-image", response_model=VLMImageAnalysisResponse)
async def analyze_image(
    file: UploadFile = File(...),
    model: str = Form(None),
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

    # Use default model if not specified
    if model is None:
        model = DEFAULT_VLM_MODEL

    log_info("=" * 50)
    log_info("GÖRSEL ANALİZİ BAŞLADI")
    log_info("=" * 50)
    log_info(f"Dosya: {file.filename}")
    log_info(f"Model: {model}")
    log_info(f"Analiz: Kişi={analyze_persons}, Logo={analyze_logos}, Metin={analyze_text}")

    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        log_error(f"Desteklenmeyen dosya türü: {file.content_type}")
        return VLMImageAnalysisResponse(
            success=False,
            error=f"Desteklenmeyen dosya türü: {file.content_type}. Sadece görsel dosyaları desteklenir."
        )

    try:
        # Read and encode image
        log_info("Görsel okunuyor ve encode ediliyor...")
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)
        log_info(f"Dosya boyutu: {file_size_mb:.2f} MB")

        image_base64 = encode_image_to_base64(content)
        log_success("Görsel başarıyla encode edildi")

        # Build prompt
        if custom_prompt:
            prompt = custom_prompt
            log_info("Özel prompt kullanılıyor")
        else:
            prompt = PERSON_LOGO_PROMPT
            log_info("Standart analiz promptu kullanılıyor")

        # Call VLM
        log_info("Model çağrılıyor, lütfen bekleyin...")
        result = await call_vlm(model, image_base64, prompt)

        raw_response = result.get("response", "")
        log_info("Yanıt parse ediliyor...")
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

        # Log results summary
        log_info("-" * 50)
        log_success(f"ANALİZ TAMAMLANDI - {processing_time/1000:.1f} saniye")
        log_info(f"Tespit edilen kişi sayısı: {len(persons)}")
        for p in persons:
            log_info(f"  - {p.name} ({p.title or 'unvan yok'}) [%{int(p.confidence*100)}]")
        log_info(f"Tespit edilen logo sayısı: {len(logos)}")
        for l in logos:
            log_info(f"  - {l.company} [%{int(l.confidence*100)}]")
        log_info(f"Tespit edilen metin sayısı: {len(texts)}")
        log_info("=" * 50)

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
        log_error(f"Analiz hatası: {str(e)}")
        log_error(traceback.format_exc())
        return VLMImageAnalysisResponse(
            success=False,
            error=str(e) + "\n" + traceback.format_exc(),
            processing_time_ms=(time.time() - start_time) * 1000
        )


async def analyze_single_frame(
    model: str,
    frame_path: str,
    timestamp: float,
    frame_num: int
) -> Tuple[int, VideoFrame, List[str], List[str]]:
    """Analyze a single frame - used for parallel processing"""
    ts_formatted = format_timestamp(timestamp)

    with open(frame_path, 'rb') as f:
        frame_bytes = f.read()

    frame_base64 = encode_image_to_base64(frame_bytes)

    # Call VLM
    result = await call_vlm(model, frame_base64, PERSON_LOGO_PROMPT, f"Kare {frame_num}")
    parsed = parse_vlm_response(result.get("response", ""))

    # Extract persons
    frame_persons = []
    person_names = []
    for p in parsed.get("persons", []):
        person = DetectedPerson(
            name=p.get("name", "Bilinmeyen"),
            title=p.get("title"),
            confidence=float(p.get("confidence", 0.9))
        )
        frame_persons.append(person)
        person_names.append(person.name)

    # Extract logos
    frame_logos = []
    logo_names = []
    for l in parsed.get("logos", []):
        logo = DetectedLogo(
            company=l.get("company", "Bilinmeyen"),
            confidence=float(l.get("confidence", 0.9))
        )
        frame_logos.append(logo)
        logo_names.append(logo.company)

    video_frame = VideoFrame(
        timestamp=timestamp,
        timestamp_formatted=ts_formatted,
        persons=frame_persons,
        logos=frame_logos,
        scene_description=parsed.get("scene_description", "")
    )

    return frame_num, video_frame, person_names, logo_names


@router.post("/analyze-video", response_model=VLMVideoAnalysisResponse)
async def analyze_video(
    file: UploadFile = File(...),
    model: str = Form(None),  # Will use DEFAULT_VLM_MODEL
    frame_interval: float = Form(5.0),
    max_frames: int = Form(50),
    batch_size: int = Form(None),  # Will use PARALLEL_BATCH_SIZE
    analyze_persons: bool = Form(True),
    analyze_logos: bool = Form(True)
):
    """
    Analyze video using Vision Language Model with PARALLEL batch processing.
    Optimized for ASUS Ascent GX10 (Grace Blackwell 128GB unified memory).
    """
    start_time = time.time()

    # Use defaults if not specified
    if model is None:
        model = DEFAULT_VLM_MODEL
    if batch_size is None:
        batch_size = PARALLEL_BATCH_SIZE

    log_info("=" * 60)
    log_info("VIDEO ANALİZİ BAŞLADI (PARALEL MOD)")
    log_info("=" * 60)
    log_info(f"Dosya: {file.filename}")
    log_info(f"Model: {model}")
    log_info(f"Paralel batch boyutu: {batch_size} kare aynı anda")
    log_info(f"Kare aralığı: {frame_interval} saniye")
    log_info(f"Maksimum kare: {max_frames}")

    # Validate file type
    valid_types = ['video/mp4', 'video/webm', 'video/x-msvideo', 'video/quicktime', 'video/x-matroska']
    if not file.content_type or not any(file.content_type.startswith(t) for t in valid_types):
        log_error(f"Desteklenmeyen dosya türü: {file.content_type}")
        return VLMVideoAnalysisResponse(
            success=False,
            error=f"Desteklenmeyen dosya türü: {file.content_type}. MP4, WEBM, AVI, MOV, MKV desteklenir."
        )

    tmp_video_path = None
    temp_dir = None

    try:
        # Save video to temp file
        log_info("Video okunuyor...")
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)
        log_info(f"Dosya boyutu: {file_size_mb:.2f} MB")

        suffix = os.path.splitext(file.filename)[1] if file.filename else '.mp4'

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_video_path = tmp.name

        log_success("Video geçici dosyaya kaydedildi")

        # Extract frames
        log_info("Kareler çıkarılıyor (FFmpeg)...")
        frames_data, duration, temp_dir = extract_video_frames(
            tmp_video_path, frame_interval, max_frames
        )

        log_success(f"Video süresi: {format_timestamp(duration)} ({duration:.1f} saniye)")
        log_success(f"Çıkarılan kare sayısı: {len(frames_data)}")

        if not frames_data:
            log_error("Video kareleri çıkarılamadı!")
            return VLMVideoAnalysisResponse(
                success=False,
                error="Video kareleri çıkarılamadı. FFmpeg kurulu olduğundan emin olun."
            )

        # Ensure model is loaded before parallel processing
        log_info("Model yükleniyor (ilk kez)...")
        await ensure_model_available(model)

        # WORKER POOL - Biri bitince hemen sıradaki başlar
        log_info("-" * 60)
        log_info(f"WORKER POOL MOD ({batch_size} worker aynı anda)")
        log_info("-" * 60)

        video_frames_dict = {}
        all_persons = set()
        all_logos = set()
        total_frames = len(frames_data)

        # Progress tracking
        completed_count = 0
        completed_lock = asyncio.Lock()

        # Semaphore - max concurrent workers
        semaphore = asyncio.Semaphore(batch_size)

        async def process_frame_with_semaphore(frame_data, frame_num):
            """Process single frame with semaphore control"""
            nonlocal completed_count

            async with semaphore:
                timestamp, frame_path = frame_data
                frame_start = time.time()

                try:
                    result = await analyze_single_frame(model, frame_path, timestamp, frame_num)
                    frame_duration = time.time() - frame_start

                    # Update progress
                    async with completed_lock:
                        completed_count += 1
                        current = completed_count

                    _, video_frame, person_names, logo_names = result

                    # Log completion
                    detections = []
                    if person_names:
                        detections.append(f"{len(person_names)} kişi")
                    if logo_names:
                        detections.append(f"{len(logo_names)} logo")
                    det_str = ", ".join(detections) if detections else "tespit yok"

                    log_progress(current, total_frames,
                        f"Kare {frame_num} tamamlandı ({frame_duration:.1f}s) - {det_str}")

                    return result

                except Exception as e:
                    async with completed_lock:
                        completed_count += 1
                    log_error(f"Kare {frame_num} hatası: {e}")
                    return None

        # Start ALL tasks at once - semaphore controls concurrency
        log_info(f"Tüm {total_frames} kare kuyruğa alındı, {batch_size} worker çalışıyor...")

        tasks = [
            process_frame_with_semaphore(frame_data, idx + 1)
            for idx, frame_data in enumerate(frames_data)
        ]

        # Run all with semaphore limiting concurrency
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect results
        for result in results:
            if result is None or isinstance(result, Exception):
                continue
            frame_num, video_frame, person_names, logo_names = result
            video_frames_dict[frame_num] = video_frame
            all_persons.update(person_names)
            all_logos.update(logo_names)

        # Sort frames by frame number
        video_frames = [video_frames_dict[i] for i in sorted(video_frames_dict.keys())]

        processing_time = (time.time() - start_time) * 1000
        per_frame_avg = (processing_time / 1000) / total_frames if total_frames > 0 else 0

        # Final summary
        log_info("=" * 60)
        log_success("VIDEO ANALİZİ TAMAMLANDI")
        log_info("=" * 60)
        log_info(f"Toplam süre: {processing_time/1000:.1f} saniye")
        log_info(f"Ortalama: {per_frame_avg:.1f} saniye/kare (paralel)")
        log_info(f"Analiz edilen kare: {len(video_frames)}")
        log_info(f"Benzersiz kişi sayısı: {len(all_persons)}")
        for p in sorted(all_persons):
            log_info(f"  - {p}")
        log_info(f"Benzersiz logo sayısı: {len(all_logos)}")
        for l in sorted(all_logos):
            log_info(f"  - {l}")
        log_info("=" * 60)

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
        log_error(f"Video analiz hatası: {str(e)}")
        log_error(traceback.format_exc())
        return VLMVideoAnalysisResponse(
            success=False,
            error=str(e) + "\n" + traceback.format_exc(),
            processing_time_ms=(time.time() - start_time) * 1000
        )

    finally:
        # Cleanup
        if tmp_video_path and os.path.exists(tmp_video_path):
            os.unlink(tmp_video_path)
            log_info("Geçici video dosyası temizlendi")

        if temp_dir and os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            log_info("Geçici kare dosyaları temizlendi")


@router.post("/vlm-chat")
async def vlm_chat(
    file: UploadFile = File(...),
    message: str = Form(...),
    model: str = Form(None)
):
    """
    Chat with VLM about an image. Ask any question about the image content.
    """
    start_time = time.time()

    # Use default model if not specified
    if model is None:
        model = DEFAULT_VLM_MODEL

    log_info("=" * 50)
    log_info("VLM SOHBET BAŞLADI")
    log_info("=" * 50)
    log_info(f"Dosya: {file.filename}")
    log_info(f"Model: {model}")
    log_info(f"Soru: {message[:100]}{'...' if len(message) > 100 else ''}")

    if not file.content_type or not file.content_type.startswith('image/'):
        log_error("Desteklenmeyen dosya türü")
        return {
            "success": False,
            "error": "Sadece görsel dosyaları desteklenir."
        }

    try:
        content = await file.read()
        file_size_mb = len(content) / (1024 * 1024)
        log_info(f"Dosya boyutu: {file_size_mb:.2f} MB")

        image_base64 = encode_image_to_base64(content)

        # Add Turkish context to the prompt
        prompt = f"""Türkçe yanıt ver. {message}"""

        log_info("Model çağrılıyor...")
        result = await call_vlm(model, image_base64, prompt)

        processing_time = (time.time() - start_time) * 1000
        response_text = result.get("response", "")

        log_success(f"SOHBET TAMAMLANDI - {processing_time/1000:.1f} saniye")
        log_info(f"Yanıt uzunluğu: {len(response_text)} karakter")
        log_info("=" * 50)

        return {
            "success": True,
            "response": response_text,
            "processing_time_ms": processing_time,
            "model_used": model
        }

    except Exception as e:
        log_error(f"Sohbet hatası: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "processing_time_ms": (time.time() - start_time) * 1000
        }
