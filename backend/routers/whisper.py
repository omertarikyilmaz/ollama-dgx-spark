"""Whisper speech-to-text endpoints"""
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

WHISPER_MODELS = [
    WhisperModelInfo(name="turbo", size="809M", description="En hızlı, yüksek doğruluk", recommended=True),
    WhisperModelInfo(name="large-v3", size="1550M", description="En yüksek doğruluk"),
    WhisperModelInfo(name="medium", size="769M", description="Dengeli hız/doğruluk"),
    WhisperModelInfo(name="small", size="244M", description="Hızlı, iyi doğruluk"),
    WhisperModelInfo(name="base", size="74M", description="Çok hızlı, orta doğruluk"),
    WhisperModelInfo(name="tiny", size="39M", description="Ultra hızlı, düşük doğruluk"),
]


def get_whisper_model(model_name: str = "turbo"):
    """Lazy load Whisper model with GPU support (Blackwell compatible)"""
    global _whisper_model, _whisper_model_name, _whisper_device

    if _whisper_model is None or _whisper_model_name != model_name:
        import whisper
        import torch

        if torch.cuda.is_available():
            _whisper_device = "cuda"
            device_name = torch.cuda.get_device_name(0)
            print(f"CUDA available: {device_name}")
        else:
            _whisper_device = "cpu"
            print("CUDA not available, using CPU")

        print(f"Loading Whisper model '{model_name}' on {_whisper_device}...")
        _whisper_model = whisper.load_model(model_name, device=_whisper_device)

        if _whisper_device == "cuda":
            try:
                _whisper_model = torch.compile(_whisper_model, mode="reduce-overhead")
                print("torch.compile() enabled - extra 20-40% speed boost!")
            except Exception as e:
                print(f"torch.compile() skipped: {e}")

        _whisper_model_name = model_name
        print(f"Whisper model '{model_name}' loaded successfully!")

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
    model: str = Form("turbo"),
    language: str = Form(None),
    task: str = Form("transcribe")
):
    """
    Transcribe audio file using OpenAI Whisper.
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

            options = {
                "task": task,
                "language": language,
                "fp16": _whisper_device == "cuda",
                "verbose": False,
            }

            result = whisper_model.transcribe(tmp_path, **options)

            segments = []
            for i, seg in enumerate(result.get("segments", [])):
                segments.append(WhisperSegment(
                    id=i,
                    start=seg["start"],
                    end=seg["end"],
                    text=seg["text"].strip(),
                    avg_logprob=seg.get("avg_logprob"),
                    no_speech_prob=seg.get("no_speech_prob")
                ))

            duration = segments[-1].end if segments else 0.0
            processing_time = (time.time() - start_time) * 1000

            return WhisperTranscriptionResponse(
                success=True,
                text=result["text"].strip(),
                segments=segments,
                language=result.get("language", "unknown"),
                language_probability=0.95,
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
    """Check if Whisper service is ready"""
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

        return {
            "status": "ready",
            "engine": "openai-whisper",
            "cuda_available": cuda_available,
            "device": device_name,
            "cuda_version": cuda_version,
            "torch_version": torch_version,
            "current_model": _whisper_model_name,
            "available_models": [m.name for m in WHISPER_MODELS]
        }
    except ImportError as e:
        return {"status": "not_installed", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
