"""Whisper speech-to-text endpoints - Faster-Whisper (CTranslate2) for 4-6x speed"""
import os
import tempfile
import time
from fastapi import APIRouter, UploadFile, File, Form
from models import WhisperTranscriptionResponse, WhisperSegment, WhisperModelInfo

router = APIRouter(tags=["Whisper"])

# Global whisper model (lazy loaded)
_whisper_model = None
_whisper_model_name = None
_whisper_device = None
_compute_type = None

WHISPER_MODELS = [
    WhisperModelInfo(name="large-v3-turbo", size="809M", description="En hızlı, yüksek doğruluk (4-6x faster)", recommended=True),
    WhisperModelInfo(name="large-v3", size="1550M", description="En yüksek doğruluk"),
    WhisperModelInfo(name="medium", size="769M", description="Dengeli hız/doğruluk"),
    WhisperModelInfo(name="small", size="244M", description="Hızlı, iyi doğruluk"),
    WhisperModelInfo(name="base", size="74M", description="Çok hızlı, orta doğruluk"),
    WhisperModelInfo(name="tiny", size="39M", description="Ultra hızlı, düşük doğruluk"),
]


def get_whisper_model(model_name: str = "large-v3-turbo"):
    """Lazy load Faster-Whisper model with GPU support (4-6x faster than openai-whisper)"""
    global _whisper_model, _whisper_model_name, _whisper_device, _compute_type

    if _whisper_model is None or _whisper_model_name != model_name:
        from faster_whisper import WhisperModel
        import torch

        if torch.cuda.is_available():
            _whisper_device = "cuda"
            # float16 for GPU - best speed/accuracy balance
            _compute_type = "float16"
            device_name = torch.cuda.get_device_name(0)
            print(f"CUDA available: {device_name}")
        else:
            _whisper_device = "cpu"
            # int8 for CPU - fastest
            _compute_type = "int8"
            print("CUDA not available, using CPU with int8 quantization")

        print(f"Loading Faster-Whisper model '{model_name}' on {_whisper_device} ({_compute_type})...")

        _whisper_model = WhisperModel(
            model_name,
            device=_whisper_device,
            compute_type=_compute_type,
            num_workers=4,  # Parallel processing
            cpu_threads=8   # For CPU fallback
        )

        _whisper_model_name = model_name
        print(f"Faster-Whisper model '{model_name}' loaded successfully! (4-6x faster)")

    return _whisper_model


@router.get("/whisper-models")
async def list_whisper_models():
    """List available Whisper models"""
    return {
        "models": [m.model_dump() for m in WHISPER_MODELS],
        "current_model": _whisper_model_name
    }


@router.post("/transcribe", response_model=WhisperTranscriptionResponse)
async def transcribe_audio(
    file: UploadFile = File(...),
    model: str = Form("large-v3-turbo"),
    language: str = Form(None),
    task: str = Form("transcribe")
):
    """
    Transcribe audio using Faster-Whisper (CTranslate2).
    4-6x faster than OpenAI Whisper with same accuracy.
    Supports: MP3, WAV, M4A, FLAC, OGG, WEBM, MP4
    """
    start_time = time.time()

    allowed_types = ['audio/', 'video/mp4', 'video/webm']
    if not file.content_type or not any(file.content_type.startswith(t) for t in allowed_types):
        return WhisperTranscriptionResponse(
            success=False,
            error=f"Desteklenmeyen dosya türü: {file.content_type}. Desteklenen: MP3, WAV, M4A, FLAC, OGG, WEBM, MP4"
        )

    try:
        content = await file.read()
        suffix = os.path.splitext(file.filename)[1] if file.filename else '.mp3'

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            whisper_model = get_whisper_model(model)

            # Faster-Whisper transcribe API
            segments_iter, info = whisper_model.transcribe(
                tmp_path,
                task=task,
                language=language,
                beam_size=5,
                vad_filter=True,  # Voice Activity Detection - skip silence
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=400
                )
            )

            # Collect segments
            segments = []
            full_text = []
            for i, seg in enumerate(segments_iter):
                segments.append(WhisperSegment(
                    id=i,
                    start=seg.start,
                    end=seg.end,
                    text=seg.text.strip(),
                    avg_logprob=seg.avg_logprob,
                    no_speech_prob=seg.no_speech_prob
                ))
                full_text.append(seg.text.strip())

            duration = segments[-1].end if segments else 0.0
            processing_time = (time.time() - start_time) * 1000

            return WhisperTranscriptionResponse(
                success=True,
                text=" ".join(full_text),
                segments=segments,
                language=info.language,
                language_probability=info.language_probability,
                duration=duration,
                processing_time_ms=processing_time,
                model_used=model
            )

        finally:
            os.unlink(tmp_path)

    except Exception as e:
        import traceback
        return WhisperTranscriptionResponse(
            success=False,
            error=str(e) + "\n" + traceback.format_exc(),
            processing_time_ms=(time.time() - start_time) * 1000
        )


@router.get("/whisper-health")
async def whisper_health():
    """Check if Faster-Whisper service is ready"""
    try:
        import torch

        cuda_available = torch.cuda.is_available()

        if cuda_available:
            device_name = torch.cuda.get_device_name(0)
            cuda_version = torch.version.cuda
            torch_version = torch.__version__
        else:
            device_name = "CPU"
            cuda_version = None
            torch_version = torch.__version__

        # Check CTranslate2 version
        ct2_version = None
        try:
            import ctranslate2
            ct2_version = ctranslate2.__version__
        except:
            pass

        return {
            "status": "ready",
            "engine": "faster-whisper (CTranslate2)",
            "speedup": "4-6x faster than openai-whisper",
            "cuda_available": cuda_available,
            "device": device_name,
            "compute_type": _compute_type,
            "cuda_version": cuda_version,
            "torch_version": torch_version,
            "ctranslate2_version": ct2_version,
            "current_model": _whisper_model_name,
            "available_models": [m.name for m in WHISPER_MODELS]
        }
    except ImportError as e:
        return {"status": "not_installed", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
