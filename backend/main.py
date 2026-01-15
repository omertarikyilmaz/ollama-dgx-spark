"""
MTM AI Hub - FastAPI Backend
Medya Takip Merkezi AI Services Platform
"""
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import PromptTemplate, KVCacheSettings
from services.ollama_client import get_ollama_client
from core.config import load_templates, load_settings, save_settings

# Import routers
from routers import health, templates, classification, chat, language, sector, link_analysis, reports, ocr, whisper, parakeet, vlm

# Global state
app_templates: Dict[str, PromptTemplate] = {}
app_settings: KVCacheSettings = KVCacheSettings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    global app_templates, app_settings
    app_templates = load_templates()
    app_settings = load_settings()

    # Initialize router states
    templates.init_state(app_templates, app_settings)
    classification.init_state(app_templates)

    yield

    # Cleanup
    client = get_ollama_client()
    await client.close()


app = FastAPI(
    title="MTM AI Hub",
    description="Medya Takip Merkezi - AI Services Platform",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(templates.router)
app.include_router(classification.router)
app.include_router(chat.router)
app.include_router(language.router)
app.include_router(sector.router)
app.include_router(link_analysis.router)
app.include_router(reports.router)
app.include_router(ocr.router)
app.include_router(whisper.router)
app.include_router(parakeet.router)
app.include_router(vlm.router)


# Settings endpoints (kept here for simplicity)
@app.get("/settings", response_model=KVCacheSettings)
async def get_settings():
    """Get current KV cache settings"""
    return app_settings


@app.put("/settings", response_model=KVCacheSettings)
async def update_settings(new_settings: KVCacheSettings):
    """Update KV cache settings"""
    global app_settings
    app_settings = new_settings
    save_settings(app_settings)
    return app_settings
