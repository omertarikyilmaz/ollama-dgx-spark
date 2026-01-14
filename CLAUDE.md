# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ollama DGX Spark is a Turkish news classification and analysis system optimized for NVIDIA DGX Spark (GB10 Grace Blackwell). It uses Ollama with KV cache optimization to provide high-speed news classification, sector analysis, language detection, and publication metadata extraction.

**Core Technologies:**
- Backend: FastAPI (Python 3.11)
- LLM Engine: Ollama (running Qwen 2.5 models)
- Frontend: Static HTML/CSS/JS served via Nginx
- Deployment: Docker Compose with GPU support

## Development Commands

### Starting the Application
```bash
# Start all services (ollama, backend, frontend)
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down
```

### Model Management
```bash
# Pull the default model (required on first run)
docker compose exec ollama ollama pull qwen2.5:32b-instruct-q4_K_M

# List available models
docker compose exec ollama ollama list

# Test Ollama health
curl http://localhost:11435/api/tags
```

### Backend Development
```bash
# Rebuild backend after code changes
docker compose up -d --build backend

# View backend logs
docker compose logs -f backend

# Test API health
curl http://localhost:8000/health
```

### Testing API Endpoints
```bash
# Health check
curl http://localhost:8000/health

# List templates
curl http://localhost:8000/templates

# Detect language
curl -X POST http://localhost:8000/detect-language \
  -H "Content-Type: application/json" \
  -d '{"text": "Merhaba dünya"}'

# Classify sector
curl -X POST http://localhost:8000/classify-sector \
  -H "Content-Type: application/json" \
  -d '{"news_text": "..."}'
```

## Architecture

### Service Layer (3 Docker Containers)

1. **ollama** (port 11435 → 11434)
   - Hosts the LLM models with GPU acceleration
   - Configured with KV cache optimization (q8_0/q4_0)
   - Keeps models in memory for faster inference
   - Environment: `OLLAMA_KV_CACHE_TYPE`, `OLLAMA_NUM_PARALLEL`, `OLLAMA_KEEP_ALIVE`

2. **backend** (port 8000)
   - FastAPI REST API
   - Communicates with Ollama via `http://ollama:11434`
   - Handles all business logic including:
     - Template management (CRUD)
     - News classification with structured JSON output
     - Language detection (using langid library)
     - Sector classification with importance levels (1-5 scale)
     - Link analysis (scrapes metadata + fetches traffic from Hypestat)
     - Excel report generation (merge multiple files, create summary with charts)
   - Data persistence: `/app/data` volume (templates.json, settings.json)

3. **frontend** (port 3001)
   - Nginx serving static files from `./frontend/`
   - Vanilla JavaScript application
   - Makes API calls to backend at `http://localhost:8000`

### Data Flow for News Classification

```
User → Frontend (app.js) → Backend (main.py) → Ollama Client (ollama_client.py) → Ollama API
                                ↓
                         Template System (templates.json)
                                ↓
                         JSON Schema Validation
                                ↓
                         Structured Output
```

### Key Backend Components

**backend/main.py** (854 lines)
- Main FastAPI application with 20+ endpoints
- Template management: `/templates` (CRUD operations)
- Classification: `/classify`, `/classify/batch`
- AI Services:
  - `/chat` - Direct LLM chat (MİNNAL AI ADMIN assistant)
  - `/detect-language` - Language detection using langid
  - `/classify-sector` - Sector classification with 5-level importance scale
  - `/analyze-link` - URL analysis (scrapes page + Hypestat traffic data)
- Report Generation:
  - `/preview-report` - Preview Excel data before generation
  - `/generate-report` - Merge Excel files, create summary with charts
  - `/export-link-analysis` - Export link analysis to Excel
- Settings: `/settings` (KV cache configuration)
- Data persistence via JSON files in `/app/data`

**backend/services/ollama_client.py**
- `OllamaClient` class: Async HTTP client for Ollama API
- `generate()`: Core method for structured JSON output
  - Builds JSON schema from template tools
  - Uses Ollama's `format` parameter for guaranteed structure
  - Returns parsed JSON + performance metrics (tokens/sec, response time)
- `health_check()`, `list_models()`, `pull_model()`
- Singleton pattern via `get_ollama_client()`

**backend/models.py**
- Pydantic models for all API requests/responses
- Core models:
  - `PromptTemplate`: KV cache template with model config
  - `ClassificationRequest/Response`
  - `SectorClassifyRequest/Response`: Includes 1-5 importance scale
  - `LinkAnalysisRequest/Response`: URL metadata + traffic data
  - `ChatRequest/Response`
  - `LanguageDetectRequest/Response`
- `ToolField`: Defines JSON schema fields for classification output

### Template System

Templates are stored in `data/templates.json` and define:
- **model**: Which Ollama model to use (e.g., qwen2.5:32b-instruct-q4_K_M)
- **prompt_desc**: System prompt describing the classification task
- **tools**: JSON schema for structured output fields (type, description, enum)
- **keep_alive**: How long to keep model in memory (e.g., "10m")
- **num_ctx**: Context window size (default 4096)
- **temperature**: Model randomness (0.0 for deterministic)

Templates enable KV cache reuse across multiple news articles with the same classification schema.

### Excel Report Generation

The system can merge multiple Excel files and generate summary reports:
- Combines multiple input files into single dataset
- Groups by "Mecra" (media type): Yazılı Basın, İnternet, TV
- Calculates totals for: Haber Adedi (news count), Erişim (reach), Reklam Eşdeğeri (ad value)
- Generates "Yönetici Özeti" sheet with summary table + pie charts
- Preserves "Tüm Veriler" sheet with all original data
- Uses xlsxwriter for formatting and chart generation
- Supports "standard" and "modern" layout styles

### Link Analysis Flow

When analyzing a URL (`/analyze-link`):
1. Validates and normalizes URL
2. Fetches HTML content (15s timeout)
3. Parses with BeautifulSoup to extract title, meta description, visible text
4. **In parallel**: Fetches traffic data from Hypestat.com (monthly/daily visitors, pageviews, global rank)
5. Sends extracted data to LLM for classification (language, content type, city, scope)
6. Returns combined metadata + traffic stats

## Configuration

### Environment Variables (.env)

```bash
# Model selection (smaller = faster, larger = better quality)
OLLAMA_MODEL=qwen2.5:32b-instruct-q4_K_M
# Alternatives: qwen2.5:14b-instruct-q4_K_M (faster)

# KV Cache optimization
OLLAMA_KV_CACHE_TYPE=q8_0  # Options: q4_0 (fastest), q8_0 (balanced), f16 (quality)

# Parallelization
OLLAMA_NUM_PARALLEL=4  # Increase for more concurrent requests

# Memory management
OLLAMA_KEEP_ALIVE=10m  # How long to keep model loaded
```

### Port Mappings
- **11435** → Ollama (11434 internal)
- **8000** → Backend API
- **3001** → Frontend

## Turkish Language Context

This is a Turkish media analysis platform. Key terminology:
- **Mecra**: Media type (Yazılı Basın = Print, İnternet = Online, TV = Television)
- **Erişim**: Reach/viewership
- **Reklam Eşdeğeri**: Advertising value equivalent
- **Haber Adedi**: News count
- **Yönetici Özeti**: Executive summary
- **Tüm Veriler**: All data
- **Sektör**: Sector
- **Önem Seviyesi**: Importance level (1=Critical, 2=Very Important, 3=Important, 4=Medium, 5=Low)

When working with prompts or responses, maintain Turkish language in system prompts and user-facing text.

## Common Tasks

### Adding a New API Endpoint
1. Define request/response models in `backend/models.py`
2. Add endpoint handler in `backend/main.py`
3. If using Ollama, call `client.generate()` with appropriate JSON schema
4. Update frontend `app.js` if UI is needed

### Modifying Classification Schema
1. Edit the template in UI or directly in `data/templates.json`
2. Update the `tools` field with new JSON schema fields
3. The system will automatically use the new schema for classification

### Changing the LLM Model
1. Update `OLLAMA_MODEL` in `.env`
2. Pull the new model: `docker compose exec ollama ollama pull <model-name>`
3. Restart backend: `docker compose restart backend`

### Debugging Ollama Issues
- Check if Ollama is running: `docker compose ps`
- View Ollama logs: `docker compose logs ollama`
- Test directly: `curl http://localhost:11435/api/tags`
- Verify GPU access: `docker compose exec ollama nvidia-smi`

## Important Notes

- **GPU Required**: This application requires NVIDIA GPU with CUDA support
- **Model Size**: The default 32B model requires ~20GB disk space and significant VRAM
- **First Request Slow**: Initial requests are slower due to KV cache building; subsequent requests are much faster
- **JSON Format**: All LLM outputs use structured JSON via Ollama's `format` parameter
- **Turkish Optimization**: System prompts and examples are in Turkish for better model performance
- **Importance Scale**: Sector classification uses 1-5 scale (1=Critical, 5=Low) with specific criteria in the system prompt
- **Excel Formulas**: Report generation uses SUM formulas in totals row for Excel compatibility
- **Traffic Data**: Link analysis fetches visitor statistics from Hypestat.com via web scraping
