# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MTM AI Hub (Medya Takip Merkezi) - A Turkish media analysis platform optimized for NVIDIA DGX Spark (GB10 Grace Blackwell). Provides news classification, sector analysis, speech-to-text transcription, OCR, and report generation using Ollama with KV cache optimization.

**Core Technologies:**
- Backend: FastAPI (Python 3.11) with modular router architecture
- LLM Engine: Ollama (Qwen 2.5 models) with structured JSON output
- Speech-to-Text: Whisper (HuggingFace Transformers) + NVIDIA Parakeet (NeMo)
- OCR: Tesseract with Turkish language support
- Frontend: Static HTML/CSS/JS served via Nginx
- Deployment: Docker Compose with GPU support

## Development Commands

### Starting the Application
```bash
docker compose up -d                    # Start all services
docker compose logs -f                  # View logs
docker compose up -d --build backend    # Rebuild backend after code changes
docker compose down                     # Stop services
```

### Model Management
```bash
docker compose exec ollama ollama pull qwen2.5:32b-instruct-q4_K_M  # Pull default model
docker compose exec ollama ollama list                               # List models
docker compose exec ollama nvidia-smi                                # Verify GPU access
```

### Testing API Endpoints
```bash
curl http://localhost:8000/health                                    # Health check
curl http://localhost:8000/templates                                 # List templates
curl http://localhost:8000/whisper-health                            # Whisper status
curl http://localhost:8000/parakeet-health                           # Parakeet status
curl http://localhost:8000/ocr-health                                # OCR status
```

## Architecture

### Service Layer (3 Docker Containers)

1. **ollama** (port 11435 → 11434): LLM with GPU acceleration, KV cache optimization
2. **backend** (port 8000): FastAPI with modular routers, data in `/app/data` volume
3. **frontend** (port 3001): Nginx serving `./frontend/` static files

### Backend Router Structure

The backend uses FastAPI routers organized by feature (`backend/routers/`):

| Router | Endpoints | Description |
|--------|-----------|-------------|
| `health.py` | `/health` | System health check |
| `templates.py` | `/templates` | CRUD for KV cache templates |
| `classification.py` | `/classify`, `/classify/batch` | News classification |
| `chat.py` | `/chat` | Direct LLM chat |
| `language.py` | `/detect-language` | Language detection (langid) |
| `sector.py` | `/classify-sector` | Sector classification (1-5 importance) |
| `link_analysis.py` | `/analyze-link` | URL scraping + Hypestat traffic |
| `reports.py` | `/preview-report`, `/generate-report`, `/export-link-analysis` | Excel generation |
| `ocr.py` | `/ocr-newspaper`, `/ocr-health` | Tesseract OCR for images |
| `whisper.py` | `/transcribe`, `/whisper-models`, `/whisper-health` | Speech-to-text (video up to 1.5h) |
| `parakeet.py` | `/parakeet-transcribe`, `/parakeet-models`, `/parakeet-health` | NVIDIA NeMo ASR |
| `vlm.py` | `/analyze-image`, `/analyze-video`, `/vlm-chat`, `/vlm-health` | Vision Language Model (Qwen VLM) |

### Key Backend Components

- **`backend/main.py`**: FastAPI app initialization, router registration, settings endpoints
- **`backend/services/ollama_client.py`**: Async Ollama client with `generate()` for structured JSON output
- **`backend/models.py`**: Pydantic models for all API requests/responses
- **`backend/core/config.py`**: Template and settings persistence (`data/templates.json`, `data/settings.json`)

### Template System

Templates in `data/templates.json` define classification schemas:
- `model`: Ollama model name
- `prompt_desc`: System prompt
- `tools`: JSON schema for output fields (type, description, enum)
- `keep_alive`, `num_ctx`, `temperature`: Model parameters

### Speech-to-Text Options

**Whisper** (HuggingFace Transformers + SDPA):
- Models: `large-v3-turbo` (recommended), `distil-turkish`, `large-v3`, `medium`, `small`
- Supports audio + video (MP4, WEBM, AVI, MKV, MOV) up to 1.5 hours
- Auto-extracts audio from video using FFmpeg

**Parakeet** (NVIDIA NeMo):
- Models: `nvidia/parakeet-rnnt-1.1b` (Turkish support), `parakeet-tdt-0.6b-v2` (English only)
- Ultra-fast (~1500x RTF), requires 16kHz mono WAV input (auto-converted)

### Vision Language Model (VLM)

**Qwen VLM** for image/video analysis:
- Models: `qwen2.5vl:32b` (recommended), `qwen2.5vl:72b`, `qwen3-vl:32b`, `qwen3-vl:8b`
- Capabilities:
  - Person detection with name reading from captions
  - Company logo identification
  - Text extraction (OCR) in 29+ languages including Turkish
  - Video analysis with timestamp-based frame extraction
- Video analysis extracts frames at configurable intervals (default 5s)

## Configuration

### Environment Variables (.env)
```bash
OLLAMA_MODEL=qwen2.5:32b-instruct-q4_K_M   # Model selection
OLLAMA_KV_CACHE_TYPE=q8_0                   # q4_0 (fastest), q8_0 (balanced), f16 (quality)
OLLAMA_NUM_PARALLEL=4                       # Concurrent requests
OLLAMA_KEEP_ALIVE=10m                       # Model memory retention
```

### Port Mappings
- **11435**: Ollama API
- **8000**: Backend API
- **3001**: Frontend

## Turkish Language Context

Key terminology used throughout:
- **Mecra**: Media type (Yazılı Basın = Print, İnternet = Online, TV = Television)
- **Erişim**: Reach/viewership
- **Reklam Eşdeğeri**: Advertising value equivalent
- **Önem Seviyesi**: Importance level (1=Critical, 2=Very Important, 3=Important, 4=Medium, 5=Low)
- **Yönetici Özeti**: Executive summary

Maintain Turkish in system prompts and user-facing text.

## Common Tasks

### Adding a New API Endpoint
1. Create router in `backend/routers/` or add to existing router
2. Define request/response models in `backend/models.py`
3. Import and register router in `backend/main.py`
4. If using Ollama, call `client.generate()` with JSON schema

### Adding a New Whisper Model
1. Add model mapping in `backend/routers/whisper.py` → `MODEL_MAPPING`
2. Add model info to `WHISPER_MODELS` list

### Debugging Ollama Issues
```bash
docker compose ps                              # Check services
docker compose logs ollama                     # View Ollama logs
curl http://localhost:11435/api/tags           # Test Ollama directly
```

## Important Notes

- **GPU Required**: NVIDIA GPU with CUDA support required for all services
- **First Request Slow**: Initial LLM/Whisper requests slower due to model loading/KV cache building
- **Video Transcription**: Whisper auto-converts video to audio via FFmpeg (max 1.5 hours)
- **Audio Preprocessing**: Parakeet requires 16kHz mono - FFmpeg auto-converts input
