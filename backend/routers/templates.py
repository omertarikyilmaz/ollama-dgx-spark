"""Template management endpoints"""
import uuid
from fastapi import APIRouter, HTTPException
from models import PromptTemplate, TemplateListResponse, KVCacheSettings
from core.config import save_templates, save_settings

router = APIRouter(prefix="/templates", tags=["Templates"])

# These will be injected from main.py
templates = {}
settings = KVCacheSettings()


def init_state(t, s):
    global templates, settings
    templates = t
    settings = s


@router.get("", response_model=TemplateListResponse)
async def get_templates():
    """List all prompt templates"""
    return TemplateListResponse(
        templates=list(templates.values()),
        count=len(templates)
    )


@router.get("/{template_id}", response_model=PromptTemplate)
async def get_template(template_id: str):
    """Get a specific template"""
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    return templates[template_id]


@router.post("", response_model=PromptTemplate)
async def create_template(template: PromptTemplate):
    """Create a new template"""
    template_id = str(uuid.uuid4())[:8]
    template.id = template_id
    templates[template_id] = template
    save_templates(templates)
    return template


@router.put("/{template_id}", response_model=PromptTemplate)
async def update_template(template_id: str, template: PromptTemplate):
    """Update an existing template"""
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    template.id = template_id
    templates[template_id] = template
    save_templates(templates)
    return template


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    """Delete a template"""
    if template_id not in templates:
        raise HTTPException(status_code=404, detail="Template not found")
    del templates[template_id]
    save_templates(templates)
    return {"deleted": template_id}
