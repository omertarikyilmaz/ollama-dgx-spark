"""NVIDIA Parakeet ultra-fast speech-to-text endpoints"""
import os
import tempfile
import time
import soundfile as sf
import numpy as np
from fastapi import APIRouter, UploadFile, File, Form
from models import ParakeetTranscriptionResponse, ParakeetSegment, ParakeetModelInfo

router = APIRouter(tags=["Parakeet"])

# Target sample rate for Parakeet (16kHz mono required)
TARGET_SAMPLE_RATE = 16000


def preprocess_audio(input_path: str) -> tuple[str, float]:
    """
    Preprocess audio file for Parakeet:
    - Convert stereo to mono
    - Resample to 16kHz
    - Save as WAV
    Returns: (processed_file_path, duration_seconds)
    """
    # Read audio file
    audio_data, sample_rate = sf.read(input_path)

    # Convert stereo to mono if needed
    if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
        audio_data = np.mean(audio_data, axis=1)

    # Resample to 16kHz if needed
    if sample_rate != TARGET_SAMPLE_RATE:
        from scipy import signal
        num_samples = int(len(audio_data) * TARGET_SAMPLE_RATE / sample_rate)
        audio_data = signal.resample(audio_data, num_samples)
        sample_rate = TARGET_SAMPLE_RATE

    # Calculate duration
    duration = len(audio_data) / sample_rate

    # Save processed audio to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp:
        sf.write(tmp.name, audio_data, sample_rate)
        return tmp.name, duration

# Global parakeet model (lazy loaded)
_parakeet_model = None
_parakeet_model_name = None

PARAKEET_MODELS = [
    ParakeetModelInfo(
        name="nvidia/parakeet-rnnt-1.1b",
        size="1.1B",
        description="Ultra hizli, Turkce destekli (~1500x RTF)",
        languages=["tr", "en", "es", "de", "fr", "it", "pt", "nl", "pl", "ru", "ar", "ja", "ko", "hi"],
        recommended=True
    ),
    ParakeetModelInfo(
        name="nvidia/parakeet-tdt-0.6b-v2",
        size="600M",
        description="En hizli model (~3380x RTF, sadece Ingilizce)",
        languages=["en"]
    ),
    ParakeetModelInfo(
        name="nvidia/parakeet-ctc-1.1b",
        size="1.1B",
        description="CTC decoder, hizli ve dogru",
        languages=["en"]
    ),
]


def get_parakeet_model(model_name: str = "nvidia/parakeet-rnnt-1.1b"):
    """Lazy load Parakeet model with GPU support"""
    global _parakeet_model, _parakeet_model_name

    if _parakeet_model is None or _parakeet_model_name != model_name:
        import torch
        import nemo.collections.asr as nemo_asr

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading Parakeet model '{model_name}' on {device}...")

        _parakeet_model = nemo_asr.models.ASRModel.from_pretrained(model_name)

        if device == "cuda":
            _parakeet_model = _parakeet_model.cuda()
            print(f"GPU: {torch.cuda.get_device_name(0)}")

        _parakeet_model.eval()
        _parakeet_model_name = model_name
        print(f"Parakeet model '{model_name}' loaded successfully!")

    return _parakeet_model


@router.get("/parakeet-models")
async def list_parakeet_models():
    """List available Parakeet models"""
    return {
        "models": [m.model_dump() for m in PARAKEET_MODELS],
        "current_model": _parakeet_model_name
    }


@router.post("/parakeet-transcribe", response_model=ParakeetTranscriptionResponse)
async def parakeet_transcribe(
    file: UploadFile = File(...),
    model: str = Form("nvidia/parakeet-rnnt-1.1b"),
    timestamps: bool = Form(True)
):
    """
    Transcribe audio using NVIDIA Parakeet (ultra-fast).
    Supports: WAV, FLAC (16kHz mono recommended)
    """
    start_time = time.time()

    allowed_types = ['audio/']
    if not file.content_type or not any(file.content_type.startswith(t) for t in allowed_types):
        return ParakeetTranscriptionResponse(
            success=False,
            error=f"Desteklenmeyen dosya turu: {file.content_type}. WAV veya FLAC kullanin."
        )

    tmp_path = None
    processed_path = None

    try:
        content = await file.read()
        suffix = os.path.splitext(file.filename)[1] if file.filename else '.wav'

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Preprocess audio: convert to mono 16kHz WAV
        processed_path, duration = preprocess_audio(tmp_path)

        try:
            parakeet_model = get_parakeet_model(model)

            if timestamps:
                output = parakeet_model.transcribe([processed_path], timestamps=True)
                result_text = output[0].text if hasattr(output[0], 'text') else str(output[0])

                segments = []
                if hasattr(output[0], 'timestamp') and output[0].timestamp:
                    ts_data = output[0].timestamp
                    if 'segment' in ts_data:
                        for seg in ts_data['segment']:
                            segments.append(ParakeetSegment(
                                start=seg.get('start', 0.0),
                                end=seg.get('end', 0.0),
                                text=seg.get('segment', '')
                            ))
                    elif 'word' in ts_data:
                        for word in ts_data['word']:
                            segments.append(ParakeetSegment(
                                start=word.get('start', 0.0),
                                end=word.get('end', 0.0),
                                text=word.get('word', '')
                            ))
            else:
                output = parakeet_model.transcribe([processed_path])
                result_text = output[0] if isinstance(output[0], str) else str(output[0])
                segments = []

            processing_time = (time.time() - start_time) * 1000
            processing_time_sec = processing_time / 1000
            rtf = duration / processing_time_sec if processing_time_sec > 0 else 0

            return ParakeetTranscriptionResponse(
                success=True,
                text=result_text.strip() if result_text else "",
                segments=segments,
                language="tr",
                duration=duration,
                processing_time_ms=processing_time,
                rtf=rtf,
                model_used=model
            )

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
            if processed_path and os.path.exists(processed_path):
                os.unlink(processed_path)

    except Exception as e:
        import traceback
        return ParakeetTranscriptionResponse(
            success=False,
            error=str(e) + "\n" + traceback.format_exc(),
            processing_time_ms=(time.time() - start_time) * 1000
        )


@router.get("/parakeet-health")
async def parakeet_health():
    """Check if Parakeet service is ready"""
    try:
        import torch

        cuda_available = torch.cuda.is_available()

        if cuda_available:
            device_name = torch.cuda.get_device_name(0)
            cuda_version = torch.version.cuda
        else:
            device_name = "CPU"
            cuda_version = None

        nemo_version = None
        try:
            import nemo
            nemo_version = nemo.__version__
        except:
            pass

        return {
            "status": "ready",
            "engine": "NVIDIA NeMo Parakeet",
            "cuda_available": cuda_available,
            "device": device_name,
            "cuda_version": cuda_version,
            "nemo_version": nemo_version,
            "current_model": _parakeet_model_name,
            "available_models": [m.name for m in PARAKEET_MODELS]
        }
    except ImportError as e:
        return {"status": "not_installed", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
