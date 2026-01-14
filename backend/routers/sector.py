"""Sector classification endpoint"""
from fastapi import APIRouter, HTTPException
from models import SectorClassifyRequest, SectorClassifyResponse
from services.ollama_client import get_ollama_client

router = APIRouter(tags=["Sector"])


@router.post("/classify-sector", response_model=SectorClassifyResponse)
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
