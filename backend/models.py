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


# ============== Link Analysis Models ==============

class LinkAnalysisRequest(BaseModel):
    url: str = Field(..., description="URL to analyze")


class LinkAnalysisResponse(BaseModel):
    url: str
    domain: str
    title: Optional[str] = None
    language: str
    content_type: str = Field(..., description="Aktüel, Spor, Ekonomi, Magazin, Teknoloji, Sağlık, Kültür-Sanat")
    city: Optional[str] = Field(None, description="Yayının odaklandığı şehir veya null")
    scope: str = Field(..., description="Lokal, Bölgesel, Ulusal, Uluslararası")
    # Traffic data from Hypestat
    monthly_visitors: Optional[str] = Field(None, description="Tahmini aylık ziyaretçi sayısı")
    daily_visitors: Optional[str] = Field(None, description="Günlük ziyaretçi sayısı")
    daily_pageviews: Optional[str] = Field(None, description="Günlük sayfa görüntüleme")
    global_rank: Optional[str] = Field(None, description="Global sıralama (HypeRank)")
    confidence: float


# ============== Newspaper OCR Models ==============

class OCRWord(BaseModel):
    """Single word with bounding box"""
    text: str
    bbox: List[List[float]] = Field(..., description="4 corner coordinates [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]")
    confidence: float


class OCRLine(BaseModel):
    """Single line of text"""
    text: str
    bbox: List[List[float]]
    confidence: float
    words: List[OCRWord] = []


class NewspaperOCRResponse(BaseModel):
    """Response from newspaper OCR"""
    success: bool
    full_text: str = Field(default="", description="Full extracted text")
    lines: List[OCRLine] = Field(default_factory=list, description="Lines with bounding boxes")
    word_count: int = 0
    processing_time_ms: float = 0
    image_width: int = 0
    image_height: int = 0
    error: Optional[str] = None


# ============== Whisper Speech-to-Text Models ==============

class WhisperSegment(BaseModel):
    """Single transcription segment"""
    id: int
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str
    avg_logprob: Optional[float] = None
    no_speech_prob: Optional[float] = None


class WhisperTranscriptionResponse(BaseModel):
    """Response from Whisper transcription"""
    success: bool
    text: str = Field(default="", description="Full transcribed text")
    segments: List[WhisperSegment] = Field(default_factory=list, description="Segments with timestamps")
    language: str = Field(default="", description="Detected language")
    language_probability: float = Field(default=0.0, description="Language detection confidence")
    duration: float = Field(default=0.0, description="Audio duration in seconds")
    processing_time_ms: float = 0
    model_used: str = Field(default="", description="Whisper model used")
    error: Optional[str] = None


class WhisperModelInfo(BaseModel):
    """Information about available Whisper models"""
    name: str
    size: str
    description: str
    recommended: bool = False


# ============== NVIDIA Parakeet ASR Models ==============

class ParakeetSegment(BaseModel):
    """Single transcription segment from Parakeet"""
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str


class ParakeetTranscriptionResponse(BaseModel):
    """Response from Parakeet transcription"""
    success: bool
    text: str = Field(default="", description="Full transcribed text")
    segments: List[ParakeetSegment] = Field(default_factory=list, description="Segments with timestamps")
    language: str = Field(default="tr", description="Language code")
    duration: float = Field(default=0.0, description="Audio duration in seconds")
    processing_time_ms: float = 0
    rtf: float = Field(default=0.0, description="Real-time factor (audio_duration / processing_time)")
    model_used: str = Field(default="", description="Parakeet model used")
    error: Optional[str] = None


class ParakeetModelInfo(BaseModel):
    """Information about available Parakeet models"""
    name: str
    size: str
    description: str
    languages: List[str]
    recommended: bool = False


# ============== Vision Language Model (VLM) Models ==============

class BoundingBox(BaseModel):
    """Bounding box coordinates"""
    x1: float = Field(..., description="Left coordinate (0-1 normalized)")
    y1: float = Field(..., description="Top coordinate (0-1 normalized)")
    x2: float = Field(..., description="Right coordinate (0-1 normalized)")
    y2: float = Field(..., description="Bottom coordinate (0-1 normalized)")


class DetectedPerson(BaseModel):
    """Detected person with name and location"""
    name: str = Field(..., description="Person name (from caption/text in image)")
    title: Optional[str] = Field(None, description="Title or role if visible")
    bbox: Optional[BoundingBox] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DetectedLogo(BaseModel):
    """Detected company logo"""
    company: str = Field(..., description="Company name")
    bbox: Optional[BoundingBox] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DetectedText(BaseModel):
    """Detected text region"""
    text: str
    bbox: Optional[BoundingBox] = None
    language: str = "tr"


class VLMAnalysisRequest(BaseModel):
    """Request for VLM image analysis"""
    model: str = Field(default="qwen2.5vl:32b", description="VLM model to use")
    analyze_persons: bool = Field(default=True, description="Detect persons and read names")
    analyze_logos: bool = Field(default=True, description="Detect company logos")
    analyze_text: bool = Field(default=True, description="Extract visible text (OCR)")
    custom_prompt: Optional[str] = Field(None, description="Custom analysis prompt")


class VLMImageAnalysisResponse(BaseModel):
    """Response from VLM image analysis"""
    success: bool
    persons: List[DetectedPerson] = Field(default_factory=list)
    logos: List[DetectedLogo] = Field(default_factory=list)
    texts: List[DetectedText] = Field(default_factory=list)
    scene_description: str = Field(default="", description="Overall scene description")
    raw_response: Optional[str] = Field(None, description="Raw model response")
    processing_time_ms: float = 0
    model_used: str = ""
    error: Optional[str] = None


class VideoFrame(BaseModel):
    """Single video frame analysis result"""
    timestamp: float = Field(..., description="Frame timestamp in seconds")
    timestamp_formatted: str = Field(..., description="Formatted timestamp (HH:MM:SS)")
    persons: List[DetectedPerson] = Field(default_factory=list)
    logos: List[DetectedLogo] = Field(default_factory=list)
    scene_description: str = ""


class VLMVideoAnalysisRequest(BaseModel):
    """Request for VLM video analysis"""
    model: str = Field(default="qwen2.5vl:32b", description="VLM model to use")
    frame_interval: float = Field(default=5.0, description="Analyze every N seconds")
    max_frames: int = Field(default=50, description="Maximum frames to analyze")
    analyze_persons: bool = True
    analyze_logos: bool = True


class VLMVideoAnalysisResponse(BaseModel):
    """Response from VLM video analysis"""
    success: bool
    frames: List[VideoFrame] = Field(default_factory=list)
    unique_persons: List[str] = Field(default_factory=list, description="All unique persons found")
    unique_logos: List[str] = Field(default_factory=list, description="All unique logos found")
    video_duration: float = 0
    frames_analyzed: int = 0
    processing_time_ms: float = 0
    model_used: str = ""
    error: Optional[str] = None


class VLMModelInfo(BaseModel):
    """Information about available VLM models"""
    name: str
    size: str
    description: str
    supports_video: bool = True
    recommended: bool = False
