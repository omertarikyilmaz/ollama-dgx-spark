"""
Application configuration and data persistence
"""
import json
from pathlib import Path
from typing import Dict

from models import PromptTemplate, KVCacheSettings

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


# Language mapping for language detection
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
