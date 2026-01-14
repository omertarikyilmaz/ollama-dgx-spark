"""Link analysis endpoints"""
import io
import re
from typing import List
from urllib.parse import urlparse

import httpx
import pandas as pd
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models import LinkAnalysisRequest, LinkAnalysisResponse
from services.ollama_client import get_ollama_client

router = APIRouter(tags=["Link Analysis"])


async def fetch_hypestat_data(domain: str) -> dict:
    """Fetch traffic data from Hypestat.com"""
    hypestat_url = f"https://hypestat.com/info/{domain}"
    traffic_data = {
        "monthly_visitors": None,
        "daily_visitors": None,
        "daily_pageviews": None,
        "global_rank": None
    }

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as http_client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = await http_client.get(hypestat_url, headers=headers)
            if response.status_code != 200:
                return traffic_data

            soup = BeautifulSoup(response.text, "lxml")
            page_text = soup.get_text(separator=" ", strip=True)

            monthly_match = re.search(r'(\d+\.?\d*[KMB]?)\s*monthly\s*visitors?', page_text, re.IGNORECASE)
            if monthly_match:
                traffic_data["monthly_visitors"] = monthly_match.group(1)

            if not traffic_data["monthly_visitors"]:
                alt_match = re.search(r'about\s+(\d+\.?\d*[KMB])\s+monthly', page_text, re.IGNORECASE)
                if alt_match:
                    traffic_data["monthly_visitors"] = alt_match.group(1)

            daily_match = re.search(r'(\d+\.?\d*[KMB]?)\s*(?:daily\s*)?visitors?\s*(?:per\s*day|daily)', page_text, re.IGNORECASE)
            if daily_match:
                traffic_data["daily_visitors"] = daily_match.group(1)

            if not traffic_data["daily_visitors"]:
                alt_daily = re.search(r'receives\s+(?:approximately\s+)?(\d+\.?\d*[KMB])\s+visitors', page_text, re.IGNORECASE)
                if alt_daily:
                    traffic_data["daily_visitors"] = alt_daily.group(1)

            pv_match = re.search(r'(\d[\d,\.]*)\s*(?:page\s*)?(?:impressions|pageviews|views)\s*per\s*day', page_text, re.IGNORECASE)
            if pv_match:
                traffic_data["daily_pageviews"] = pv_match.group(1).replace(",", "")

            rank_match = re.search(r'(?:HypeRank|Global\s*Rank)[:\s#]*(\d[\d,]*)', page_text, re.IGNORECASE)
            if rank_match:
                traffic_data["global_rank"] = "#" + rank_match.group(1).replace(",", "")

    except Exception as e:
        print(f"Hypestat fetch error for {domain}: {e}")

    return traffic_data


@router.post("/analyze-link", response_model=LinkAnalysisResponse)
async def analyze_link(request: LinkAnalysisRequest):
    """Analyze a URL to extract publication metadata using AI + Hypestat traffic data"""
    url = request.url

    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            url = "https://" + url
            parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
    except Exception:
        raise HTTPException(status_code=400, detail="Geçersiz URL formatı")

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as http_client:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = await http_client.get(url, headers=headers)
            response.raise_for_status()
            html_content = response.text
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Sayfa yüklenemedi: HTTP {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Sayfa yüklenemedi: {str(e)}")

    soup = BeautifulSoup(html_content, "lxml")
    title = soup.title.string.strip() if soup.title and soup.title.string else domain

    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"]

    for script in soup(["script", "style", "nav", "footer", "header"]):
        script.decompose()
    visible_text = soup.get_text(separator=" ", strip=True)[:2000]

    hypestat_data = await fetch_hypestat_data(domain)

    analysis_prompt = f"""Aşağıdaki web sitesini analiz et:

URL: {url}
Domain: {domain}
Başlık: {title}
Meta Açıklama: {meta_desc}
Sayfa İçeriği (özet): {visible_text[:1500]}

Bu yayını analiz edip aşağıdaki bilgileri çıkar:
1. Yayının dili
2. İçerik türü (Aktüel/Genel Haber, Spor, Ekonomi, Magazin, Teknoloji, Sağlık, Kültür-Sanat, Politika)
3. Odaklandığı şehir (varsa, yoksa null)
4. Kapsam (Lokal, Bölgesel, Ulusal, Uluslararası)
"""

    json_schema = {
        "language": {"type": "string", "description": "Yayının dili (Türkçe, İngilizce, vs.)"},
        "content_type": {"type": "string", "description": "Ana içerik türü"},
        "city": {"type": "string", "description": "Yayının odaklandığı şehir veya 'Genel'"},
        "scope": {"type": "string", "description": "Kapsam: Lokal, Bölgesel, Ulusal, Uluslararası"},
        "confidence": {"type": "number", "description": "Analiz güven skoru 0-1"}
    }

    client = get_ollama_client()

    try:
        result = await client.generate(
            model="qwen2.5:32b-instruct-q4_K_M",
            prompt=analysis_prompt,
            system_prompt="Sen bir medya analiz uzmanısın. Verilen web sitesi bilgilerini analiz edip yayın hakkında bilgi çıkar. Yanıtı sadece belirtilen JSON formatında ver.",
            json_schema=json_schema,
            keep_alive="5m"
        )

        ai_result = result["result"]

        return LinkAnalysisResponse(
            url=url,
            domain=domain,
            title=title,
            language=ai_result.get("language", "Türkçe"),
            content_type=ai_result.get("content_type", "Aktüel"),
            city=ai_result.get("city") if ai_result.get("city") != "Genel" else None,
            scope=ai_result.get("scope", "Ulusal"),
            monthly_visitors=hypestat_data.get("monthly_visitors"),
            daily_visitors=hypestat_data.get("daily_visitors"),
            daily_pageviews=hypestat_data.get("daily_pageviews"),
            global_rank=hypestat_data.get("global_rank"),
            confidence=ai_result.get("confidence", 0.85)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI analizi başarısız: {str(e)}")


class LinkAnalysisExportRequest(BaseModel):
    analyses: List[dict]


@router.post("/export-link-analysis")
async def export_link_analysis(request: LinkAnalysisExportRequest):
    """Export link analysis results to Excel"""
    if not request.analyses:
        raise HTTPException(status_code=400, detail="Dışa aktarılacak veri yok")

    df = pd.DataFrame(request.analyses)

    column_map = {
        'domain': 'Domain',
        'title': 'Başlık',
        'language': 'Dil',
        'content_type': 'İçerik Türü',
        'city': 'Şehir',
        'scope': 'Kapsam',
        'monthly_visitors': 'Aylık Ziyaretçi',
        'confidence': 'Güven Skoru',
        'url': 'URL'
    }

    export_cols = ['domain', 'title', 'language', 'content_type', 'city', 'scope', 'monthly_visitors', 'confidence', 'url']
    export_df = df[[col for col in export_cols if col in df.columns]].copy()
    export_df.rename(columns=column_map, inplace=True)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        export_df.to_excel(writer, sheet_name='Yayın Analizi', index=False)

        workbook = writer.book
        worksheet = writer.sheets['Yayın Analizi']

        for i, col in enumerate(export_df.columns):
            max_len = max(export_df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, min(max_len, 50))

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#f59e0b',
            'font_color': 'white',
            'border': 1
        })
        for col_num, value in enumerate(export_df.columns.values):
            worksheet.write(0, col_num, value, header_format)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=yayin_analizi.xlsx"}
    )
