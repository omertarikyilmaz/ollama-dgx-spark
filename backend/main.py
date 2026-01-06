"""
Ollama KV Cache Template System - FastAPI Backend
Provides REST API for managing prompt templates and classifying news articles.
"""
import json
import uuid
from pathlib import Path
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from models import (
    PromptTemplate,
    ClassificationRequest,
    ClassificationResponse,
    KVCacheSettings,
    TemplateListResponse,
    KVCacheType
)
from services.ollama_client import get_ollama_client, OllamaClient


# Data storage paths
DATA_DIR = Path("/app/data")
TEMPLATES_FILE = DATA_DIR / "templates.json"
SETTINGS_FILE = DATA_DIR / "settings.json"


def load_templates() -> Dict[str, PromptTemplate]:
    """Load templates from JSON file"""
    if TEMPLATES_FILE.exists():
        with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {k: PromptTemplate(**v) for k, v in data.items()}
    return {}


def save_templates(templates: Dict[str, PromptTemplate]):
    """Save templates to JSON file"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump({k: v.model_dump() for k, v in templates.items()}, f, ensure_ascii=False, indent=2)


def load_settings() -> KVCacheSettings:
    """Load KV cache settings"""
    if SETTINGS_FILE.exists():
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return KVCacheSettings(**json.load(f))
    return KVCacheSettings()


def save_settings(settings: KVCacheSettings):
    """Save KV cache settings"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, indent=2)


# In-memory storage (persisted to JSON)
templates: Dict[str, PromptTemplate] = {}
settings: KVCacheSettings = KVCacheSettings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    global templates, settings
    templates = load_templates()
    settings = load_settings()
    yield
    # Cleanup
    client = get_ollama_client()
    await client.close()


app = FastAPI(
    title="Ollama KV Cache Template System",
    description="Manage KV cache templates for high-speed news classification",
    version="1.0.0",
    lifespan=lifespan
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Health & Status ==============

@app.get("/health")
async def health_check():
    """Check API and Ollama health"""
    client = get_ollama_client()
    ollama_ok = await client.health_check()
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "api": "ok",
        "ollama": "ok" if ollama_ok else "unavailable"
    }


@app.get("/models")
async def list_models():
    """List available Ollama models"""
    client = get_ollama_client()
    return await client.list_models()


# ============== Template Management ==============

@app.get("/templates", response_model=TemplateListResponse)
async def get_templates():
    """List all prompt templates"""
    return TemplateListResponse(
        templates=list(templates.values()),
        count=len(templates)
    )


@app.get("/templates/{template_id}", response_model=PromptTemplate)
async def get_template(template_id: str):
    """Get a specific template"""
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    return templates[template_id]


@app.post("/templates", response_model=PromptTemplate)
async def create_template(template: PromptTemplate):
    """Create a new template"""
    template_id = str(uuid.uuid4())[:8]
    template.id = template_id
    templates[template_id] = template
    save_templates(templates)
    return template


@app.put("/templates/{template_id}", response_model=PromptTemplate)
async def update_template(template_id: str, template: PromptTemplate):
    """Update an existing template"""
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    template.id = template_id
    templates[template_id] = template
    save_templates(templates)
    return template


@app.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a template"""
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    del templates[template_id]
    save_templates(templates)
    return {"deleted": template_id}


# ============== KV Cache Settings ==============

@app.get("/settings", response_model=KVCacheSettings)
async def get_settings():
    """Get current KV cache settings"""
    return settings


@app.put("/settings", response_model=KVCacheSettings)
async def update_settings(new_settings: KVCacheSettings):
    """Update KV cache settings"""
    global settings
    settings = new_settings
    save_settings(settings)
    return settings


# ============== Classification ==============

@app.post("/classify", response_model=ClassificationResponse)
async def classify_news(request: ClassificationRequest):
    """Classify a news article using the specified template"""
    if request.template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    
    template = templates[request.template_id]
    client = get_ollama_client()
    
    # Convert tools to JSON schema format
    json_schema = {}
    for field_name, field_config in template.tools.items():
        json_schema[field_name] = field_config.model_dump()
    
    try:
        result = await client.generate(
            model=template.model,
            prompt=request.news_text,
            system_prompt=template.prompt_desc,
            json_schema=json_schema,
            keep_alive=template.keep_alive,
            num_ctx=template.num_ctx,
            temperature=template.temperature
        )
        
        return ClassificationResponse(
            success=True,
            result=result["result"],
            response_time_ms=result["response_time_ms"],
            tokens_per_second=result["tokens_per_second"]
        )
    except Exception as e:
        return ClassificationResponse(
            success=False,
            error=str(e)
        )


# ============== Batch Classification ==============

@app.post("/classify/batch")
async def classify_news_batch(template_id: str, news_texts: List[str]):
    """Classify multiple news articles (uses same KV cache for efficiency)"""
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    
    results = []
    for news_text in news_texts:
        result = await classify_news(ClassificationRequest(
            template_id=template_id,
            news_text=news_text
        ))
        results.append(result)
    
    return {
        "results": results,
        "count": len(results)
    }
