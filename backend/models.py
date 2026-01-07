"""
Pydantic models for Ollama KV Cache Template System
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from enum import Enum


class KVCacheType(str, Enum):
    Q4_0 = "q4_0"
    Q8_0 = "q8_0"
    F16 = "f16"


class ToolField(BaseModel):
    """A single field in the classification schema"""
    description: str
    type: str = "string"
    enum: Optional[List[str]] = None


class PromptTemplate(BaseModel):
    """KV Cache prompt template for news classification"""
    id: Optional[str] = None
    name: str = Field(..., description="Template name")
    model: str = Field(default="qwen2.5:32b-instruct-q4_K_M", description="Ollama model name")
    prompt_desc: str = Field(..., description="System prompt describing the classification task")
    tools: Dict[str, ToolField] = Field(default_factory=dict, description="JSON schema for output fields")
    keep_alive: str = Field(default="10m", description="How long to keep model in memory")
    num_ctx: int = Field(default=4096, description="Context window size")
    temperature: float = Field(default=0.0, description="Model temperature (0 for deterministic)")


class ClassificationRequest(BaseModel):
    """Request to classify a news article"""
    template_id: str = Field(..., description="ID of the template to use")
    news_text: str = Field(..., description="News article text to classify")


class ClassificationResponse(BaseModel):
    """Response from classification"""
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    response_time_ms: Optional[float] = None
    tokens_per_second: Optional[float] = None


class KVCacheSettings(BaseModel):
    """Global KV cache settings"""
    kv_cache_type: KVCacheType = KVCacheType.Q8_0
    num_parallel: int = Field(default=4, ge=1, le=16)
    default_keep_alive: str = "10m"


class TemplateListResponse(BaseModel):
    """List of templates"""
    templates: List[PromptTemplate]
    count: int


# ============== New Service Models ==============

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    model: str = "qwen2.5:32b-instruct-q4_K_M"


class ChatResponse(BaseModel):
    response: str
    response_time_ms: float


class LanguageDetectRequest(BaseModel):
    text: str


class LanguageDetectResponse(BaseModel):
    language: str
    language_name: str
    confidence: float


class SectorClassifyRequest(BaseModel):
    news_text: str


class SectorClassifyResponse(BaseModel):
    sector: str
    subsector: str
    keywords: List[str]
    importance_level: int = Field(..., ge=1, le=5, description="1: Kritik, 2: Çok Önemli, 3: Önemli, 4: Orta, 5: Düşük")
    importance_reasoning: str = Field(..., description="Önem seviyesinin atanma gerekçesi")
    confidence: float
