"""News classification endpoints"""
from typing import List
from fastapi import APIRouter, HTTPException
from models import ClassificationRequest, ClassificationResponse
from services.ollama_client import get_ollama_client

router = APIRouter(tags=["Classification"])

# Injected from main
templates = {}


def init_state(t):
    global templates
    templates = t


@router.post("/classify", response_model=ClassificationResponse)
async def classify_news(request: ClassificationRequest):
    """Classify a news article using the specified template"""
    if request.template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")

    template = templates[request.template_id]
    client = get_ollama_client()

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
        return ClassificationResponse(success=False, error=str(e))


@router.post("/classify/batch")
async def classify_news_batch(template_id: str, news_texts: List[str]):
    """Classify multiple news articles"""
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")

    results = []
    for news_text in news_texts:
        result = await classify_news(ClassificationRequest(
            template_id=template_id,
            news_text=news_text
        ))
        results.append(result)

    return {"results": results, "count": len(results)}
