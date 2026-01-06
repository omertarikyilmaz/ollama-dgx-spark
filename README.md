# Ollama DGX Spark - Haber Sınıflandırıcı

KV Cache optimizasyonu ile hızlı haber sınıflandırma sistemi. NVIDIA DGX Spark (GB10 Grace Blackwell) için optimize edilmiştir.

## ⚡ Hızlı Başlangıç

```bash
# 1. Servisleri başlat
docker compose up -d

# 2. Modeli indir (ilk seferde ~20GB)
docker compose exec ollama ollama pull qwen2.5:32b-instruct-q4_K_M

# 3. Arayüzü aç
open http://localhost:3001
```

## 🏗️ Mimari

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Frontend   │────▶│   Backend    │────▶│   Ollama     │
│  (Nginx)    │     │  (FastAPI)   │     │   (GPU)      │
│  :3001      │     │  :8000       │     │  :11434      │
└─────────────┘     └──────────────┘     └──────────────┘
```

## 🎯 Özellikler

- **KV Cache Şablonları**: Her sektör için özel prompt şablonları oluşturun
- **JSON Yapılandırılmış Çıktı**: Her zaman tutarlı JSON formatında yanıt
- **Türkçe Destek**: Qwen 2.5 modeli ile mükemmel Türkçe anlama
- **Hız Optimizasyonu**: KV cache quantization (q4_0/q8_0) ile hızlı inference

## ⚙️ Yapılandırma

`.env` dosyasını düzenleyin:

```bash
# Model (daha küçük = daha hızlı)
OLLAMA_MODEL=qwen2.5:32b-instruct-q4_K_M

# KV Cache (q4_0 = en hızlı, q8_0 = dengeli)
OLLAMA_KV_CACHE_TYPE=q8_0

# Paralel istek sayısı
OLLAMA_NUM_PARALLEL=4
```

## 📊 API Endpoints

| Endpoint | Açıklama |
|----------|----------|
| `GET /health` | Sistem durumu |
| `GET /templates` | Şablon listesi |
| `POST /templates` | Yeni şablon |
| `POST /classify` | Haber sınıflandır |
| `GET /settings` | KV cache ayarları |

## 🚀 DGX Spark'ta Deploy

```bash
# Sunucuya kopyala
scp -r . user@dgx-spark:/home/user/ollama-dgx-spark

# SSH ile bağlan
ssh user@dgx-spark

# Başlat
cd /home/user/ollama-dgx-spark
docker compose up -d
```
