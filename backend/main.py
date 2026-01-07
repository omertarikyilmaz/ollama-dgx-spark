"""
Ollama KV Cache Template System - FastAPI Backend
Provides REST API for managing prompt templates and classifying news articles.
"""
import json
import uuid
from pathlib import Path
from typing import Dict, List
from fastapi import FastAPI, UploadFile, File, HTTPException, Body, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
import io
import pandas as pd

from models import (
    PromptTemplate,
    ClassificationRequest,
    ClassificationResponse,
    KVCacheSettings,
    TemplateListResponse,
    KVCacheType,
    ChatRequest,
    ChatResponse,
    LanguageDetectRequest,
    LanguageDetectResponse,
    SectorClassifyRequest,
    SectorClassifyResponse,
    ChatMessage
)
from services.ollama_client import get_ollama_client, OllamaClient
import langid


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


# ============== New Services ==============

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Direct chat with the AI model"""
    client = get_ollama_client()
    
    # Format chat history for the prompt if needed, 
    # but for now we'll use a simpler approach since our client currently handles single prompts.
    # We can enhance the client later for full chat history support.
    context = ""
    for msg in request.history:
        context += f"{msg.role.upper()}: {msg.content}\n"
    
    full_prompt = f"{context}USER: {request.message}\nASSISTANT:"
    
    try:
        # Using generate with a more free-form JSON schema or just text
        result = await client.generate(
            model=request.model,
            prompt=full_prompt,
            system_prompt="Sen MİNNAL AI ADMİN yardımcısısın. Medya Takip Merkezi (MTM) platformu içerisinde genel bir AI asistanı olarak görev yapıyorsun. Kullanıcıyla normal bir sohbet kur, her şeyi bir haber merkezi formatında analiz etmeye zorlama. Yardımsever, zeki ve özgün yanıtlar ver.",
            json_schema={"response": {"type": "string", "description": "The assistant's response"}},
            keep_alive="10m"
        )
        
        return ChatResponse(
            response=result["result"]["response"],
            response_time_ms=result["response_time_ms"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


LANG_MAP = {
    'af': 'Afrikanca', 'am': 'Amharca', 'an': 'Aragonca', 'ar': 'Arapça',
    'as': 'Assamca', 'az': 'Azerice', 'be': 'Belarusça', 'bg': 'Bulgarca',
    'bn': 'Bengalce', 'br': 'Bretonca', 'bs': 'Boşnakça', 'ca': 'Katalanca',
    'cs': 'Çekçe', 'cy': 'Galce', 'da': 'Danca', 'de': 'Almanca',
    'dz': 'Dzongkha', 'el': 'Yunanca', 'en': 'İngilizce', 'eo': 'Esperanto',
    'es': 'İspanyolca', 'et': 'Estonca', 'eu': 'Baskça', 'fa': 'Farsça',
    'fi': 'Fince', 'fo': 'Faroece', 'fr': 'Fransızca', 'ga': 'İrlandaca',
    'gl': 'Galiçyaca', 'gu': 'Guceratça', 'he': 'İbranice', 'hi': 'Hintçe',
    'hr': 'Hırvatça', 'ht': 'Haiti Kreyolu', 'hu': 'Macarca', 'hy': 'Ermenice',
    'id': 'Endonezyaca', 'is': 'İzlandaca', 'it': 'İtalyanca', 'ja': 'Japonca',
    'jv': 'Cavaca', 'ka': 'Gürcüce', 'kk': 'Kazakça', 'km': 'Khmer',
    'kn': 'Kannada', 'ko': 'Korece', 'ku': 'Kürtçe', 'ky': 'Kırgızca',
    'la': 'Latince', 'lb': 'Lüksemburgca', 'lo': 'Lao', 'lt': 'Litvanca',
    'lv': 'Letonca', 'mg': 'Malgaşça', 'mk': 'Makedonca', 'ml': 'Malayalam',
    'mn': 'Moğolca', 'mr': 'Marathi', 'ms': 'Malayca', 'mt': 'Maltaca',
    'nb': 'Norveççe (Bokmål)', 'ne': 'Nepalce', 'nl': 'Felemenkçe', 'nn': 'Norveççe (Nynorsk)',
    'no': 'Norveççe', 'oc': 'Oksitanca', 'or': 'Odia', 'pa': 'Pencapça',
    'pl': 'Lehçe', 'ps': 'Peştuca', 'pt': 'Portekizce', 'qu': 'Keçuva dili',
    'ro': 'Romence', 'ru': 'Rusça', 'rw': 'Ruandaca', 'se': 'Kuzey Laponca',
    'si': 'Sinhala', 'sk': 'Slovakça', 'sl': 'Slovence', 'sq': 'Arnavutça',
    'sr': 'Sırpça', 'sv': 'İsveççe', 'sw': 'Svahili', 'ta': 'Tamilce',
    'te': 'Teluguca', 'th': 'Tayca', 'tl': 'Tagalog', 'tr': 'Türkçe',
    'ug': 'Uygurca', 'uk': 'Ukraynaca', 'ur': 'Urduca', 'uz': 'Özbekçe',
    'vi': 'Vietnamca', 'wa': 'Vallonca', 'xh': 'Xhosa', 'zh': 'Çince',
    'zu': 'Zuluca'
}

@app.post("/detect-language", response_model=LanguageDetectResponse)
async def detect_language(request: LanguageDetectRequest):
    """Detect the language of the provided text using local langid library"""
    try:
        # local classification: returns (iso_code, confidence)
        iso_code, confidence = langid.classify(request.text)
        
        language_name = LANG_MAP.get(iso_code, iso_code.upper())
        
        return LanguageDetectResponse(
            language=iso_code,
            language_name=language_name,
            confidence=float(confidence) if confidence < 1 else 0.99
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/classify-sector", response_model=SectorClassifyResponse)
async def classify_sector(request: SectorClassifyRequest):
    """Classify the sector and importance level of a news article using AI"""
    client = get_ollama_client()
    
    json_schema = {
        "sector": {"type": "string", "description": "Ana sektör (örn: Teknoloji, Ekonomi, Sağlık, Spor, Siyaset, Magazin)"},
        "subsector": {"type": "string", "description": "Alt sektör veya detaylı kategori"},
        "keywords": {"type": "array", "items": {"type": "string"}, "description": "Haberle ilgili 3-5 adet anahtar kelime"},
        "importance_level": {"type": "integer", "description": "1 ile 5 arası önem seviyesi"},
        "importance_reasoning": {"type": "string", "description": "Bu önem seviyesinin neden seçildiğinin kısa açıklaması"},
        "confidence": {"type": "number", "description": "Güven skoru"}
    }
    
    system_prompt = """Sen bir medya analiz uzmanısın. Verilen haberi analiz et ve ilgili sektör, alt sektör ve önem seviyesini belirle.

Önem Skalası ve Kriterleri:
Seviye 1: KRİTİK (En Yüksek Önem) - Sektörün tamamını etkileyen, acil müdahale gerektiren büyük sistemik riskler (Doğal afet, kritik regülasyon, sistem çökmesi).
Seviye 2: ÇOK ÖNEMLİ - Yapısal değişikliklere yol açabilecek ulusal gelişmeler (Büyük birleşmeler, pazar dinamiklerini değiştiren teknolojik dönüşümler).
Seviye 3: ÖNEMLİ - Belirli segmentleri etkileyen orta vadeli gelişmeler (Yeni ürün lansmanı, sektörel raporlar, orta ölçekli yatırımlar).
Seviye 4: ORTA ÖNEM - Günlük işleyişi ilgilendiren rutin gelişmeler (Firma finansalları, personel değişiklikleri, küçük projeler).
Seviye 5: DÜŞÜK ÖNEM - Bilgilendirme amaçlı minimal etkili haberler (Küçük etkinlikler, rutin duyurular, sosyal sorumluluk).

Yanıtı sadece belirtilen JSON formatında ver."""
    
    try:
        result = await client.generate(
            model="qwen2.5:32b-instruct-q4_K_M", 
            prompt=request.news_text,
            system_prompt=system_prompt,
            json_schema=json_schema,
            keep_alive="5m"
        )
        
        return SectorClassifyResponse(
            sector=result["result"]["sector"],
            subsector=result["result"]["subsector"],
            keywords=result["result"]["keywords"],
            importance_level=result["result"]["importance_level"],
            importance_reasoning=result["result"]["importance_reasoning"],
            confidence=result["result"].get("confidence", 0.9)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



async def extract_and_merge_data(files: List[UploadFile]):
    if not files:
        raise HTTPException(status_code=400, detail="Dosya yüklenmedi")

    all_dfs = []
    errors = []
    for file in files:
        content = await file.read()
        try:
            df = pd.read_excel(io.BytesIO(content))
            all_dfs.append(df)
            file.seek(0) # Reset for potential re-use if needed, though usually consumed once
        except Exception as e:
            print(f"Error reading {file.filename}: {e}")
            continue

    if not all_dfs:
        raise HTTPException(status_code=400, detail="Geçerli bir Excel dosyası okunamadı")

    # Merge
    merged_df = pd.concat(all_dfs, ignore_index=True)
    
    # Filter NaN Mecra
    if 'Mecra' in merged_df.columns:
        merged_df = merged_df.dropna(subset=['Mecra'])

    # Mecra mapping
    def map_mecra(val):
        if pd.isna(val): return "Diğer"
        val_str = str(val).strip()
        if "Elektronik Basın" in val_str: return "İnternet"
        if "Görsel Basın" in val_str: return "TV"
        if "Yazılı Basın" in val_str: return "Yazılı Basın"
        return val_str

    if 'Mecra' in merged_df.columns:
        merged_df['Mecra_Grup'] = merged_df['Mecra'].apply(map_mecra)
    else:
        merged_df['Mecra_Grup'] = "Diğer"

    # Numeric conversion
    if 'Erişim' in merged_df.columns:
        merged_df['Erişim'] = pd.to_numeric(merged_df['Erişim'], errors='coerce').fillna(0)
    if 'Re.Eş. (TRY)' in merged_df.columns:
        merged_df['Re.Eş. (TRY)'] = pd.to_numeric(merged_df['Re.Eş. (TRY)'], errors='coerce').fillna(0)

    # Build summary
    summary = merged_df.groupby('Mecra_Grup').size().reset_index(name='Haber Adedi')
    summary.rename(columns={'Mecra_Grup': 'Mecra'}, inplace=True)
    
    if 'Erişim' in merged_df.columns:
        erisim_sum = merged_df.groupby('Mecra_Grup')['Erişim'].sum().reset_index(name='Erişim')
        summary = summary.merge(erisim_sum.rename(columns={'Mecra_Grup': 'Mecra'}), on='Mecra')
        
    if 'Re.Eş. (TRY)' in merged_df.columns:
        re_sum = merged_df.groupby('Mecra_Grup')['Re.Eş. (TRY)'].sum().reset_index(name='Reklam Eşdeğeri(TL)')
        summary = summary.merge(re_sum.rename(columns={'Mecra_Grup': 'Mecra'}), on='Mecra')

    # Sort
    order = {'Yazılı Basın': 0, 'İnternet': 1, 'TV': 2}
    summary['sort_order'] = summary['Mecra'].map(order).fillna(99)
    summary = summary.sort_values('sort_order').drop(columns=['sort_order']).reset_index(drop=True)

    return merged_df, summary

@app.post("/preview-report")
async def preview_report(files: List[UploadFile] = File(...)):
    try:
        _, summary = await extract_and_merge_data(files)
        
        # Calculate totals
        numeric_cols = summary.select_dtypes(include=['number']).columns.tolist()
        totals = summary[numeric_cols].sum()
        totals_dict = {'Mecra': 'Toplam'}
        for col in numeric_cols:
            totals_dict[col] = float(totals[col]) # Ensure native float for JSON

        # Prepare summary for JSON
        summary_records = summary.to_dict(orient='records')
        
        # Chart Data Preparation (for Chart.js)
        # We need generic structure: labels, datasets
        labels = summary['Mecra'].tolist()
        
        chart_data = {
            'labels': labels,
            'haber_adedi': summary['Haber Adedi'].tolist(),
            'erisim': summary['Erişim'].tolist() if 'Erişim' in summary.columns else [],
            'reklam': summary['Reklam Eşdeğeri(TL)'].tolist() if 'Reklam Eşdeğeri(TL)' in summary.columns else []
        }

        return {
            "success": True,
            "data": {
                "summary_table": summary_records,
                "totals": totals_dict,
                "chart_data": chart_data
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/generate-report")
async def generate_report(files: List[UploadFile] = File(...), layout_type: str = Form("standard")):
    """Merge multiple Excel files and generate a summary report with charts."""
    try:
        merged_df, summary = await extract_and_merge_data(files)
        
        # Add Totals Row for Excel
        numeric_cols = summary.select_dtypes(include=['number']).columns.tolist()
        totals = summary[numeric_cols].sum()
        totals_row = {'Mecra': 'Toplam'}
        for col in numeric_cols:
            totals_row[col] = totals[col]
        summary = pd.concat([summary, pd.DataFrame([totals_row])], ignore_index=True)

        # Create the Excel file
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            merged_df.to_excel(writer, sheet_name='Tüm Veriler', index=False)
            summary.to_excel(writer, sheet_name='Yönetici Özeti', index=False, startrow=0, startcol=0)
            
            workbook = writer.book
            summary_sheet = writer.sheets['Yönetici Özeti']
            
            # Set column widths
            summary_sheet.set_column('A:A', 15)
            summary_sheet.set_column('B:B', 12)
            summary_sheet.set_column('C:C', 15)
            summary_sheet.set_column('D:D', 20)
            
            # Style Configuration
            if layout_type == "modern":
                header_bg = '#4A90E2' # Blue
                header_font = 'white'
                chart_style = 2
            else: # standard
                header_bg = '#D7E4BC' # Green-ish
                header_font = 'black'
                chart_style = 10

            header_format = workbook.add_format({
                'bold': True, 
                'bg_color': header_bg, 
                'font_color': header_font,
                'border': 1
            })
            
            for col_num, value in enumerate(summary.columns.values):
                summary_sheet.write(0, col_num, value, header_format)
            
            # Charts logic
            data_rows = len(summary) - 1
            
            # Move charts to Row 10 with adjusted spacing and size to prevent overlap
            # Reduced scale (0.75) to fit 3 charts in one row
            # Positions: A10, G10, M10 (Gap of 6 columns)
            
            def add_chart_at(col_idx, title, pos_cell):
                add_pie_chart(col_idx, title, pos_cell, scale=0.75)

            add_pie_chart(1, 'HABER ADEDİ DAĞILIM YÜZDESİ', 'A10')
            
            col_map = {col: i for i, col in enumerate(summary.columns)}
            if 'Erişim' in col_map:
                add_pie_chart(col_map['Erişim'], 'ERİŞİM DAĞILIM YÜZDESİ', 'G10')
            
            if 'Reklam Eşdeğeri(TL)' in col_map:
                add_pie_chart(col_map['Reklam Eşdeğeri(TL)'], 'REKLAM EŞDEĞERİ (TL) DAĞILIM YÜZDESİ', 'M10')

        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=MTM_Yonetici_Ozeti.xlsx"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rapor oluşturulurken hata: {str(e)}")
