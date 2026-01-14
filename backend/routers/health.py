"""Health check endpoints"""
from fastapi import APIRouter
from services.ollama_client import get_ollama_client

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    """Check API and Ollama health"""
    client = get_ollama_client()
    ollama_ok = await client.health_check()
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "api": "ok",
        "ollama": "ok" if ollama_ok else "unavailable"
    }


@router.get("/models")
async def list_models():
    """List available Ollama models"""
    client = get_ollama_client()
    return await client.list_models()
