# 🚀 Kurulum Rehberi

Bu doküman, Ollama Haber Sınıflandırma sisteminin DGX Spark sunucusuna nasıl kurulacağını adım adım açıklar.

---

## 📋 Gereksinimler

- NVIDIA DGX Spark (GB10 Grace Blackwell)
- Docker & Docker Compose
- NVIDIA Container Toolkit
- En az 30GB boş disk alanı (model için)

---

## 1️⃣ Projeyi Sunucuya Kopyala

**Yerel bilgisayardan:**
```bash
scp -r /home/ower/Projects/mtm/ollama-dgx-spark user@<SUNUCU_IP>:~/
```

**Veya Git ile:**
```bash
ssh user@<SUNUCU_IP>
git clone <repo-url> ~/ollama-dgx-spark
```

---

## 2️⃣ Sunucuya Bağlan

```bash
ssh user@<SUNUCU_IP>
cd ~/ollama-dgx-spark
```

---

## 3️⃣ Docker Servislerini Başlat

```bash
docker compose up -d
```

Bu komut 3 servis başlatır:
- **ollama** (port 11434) - LLM engine
- **backend** (port 8000) - API
- **frontend** (port 3001) - Web arayüzü

---

## 4️⃣ Model İndir

```bash
# Önerilen model (~20GB, Türkçe destekli)
docker compose exec ollama ollama pull qwen2.5:32b-instruct-q4_K_M

# Daha hızlı alternatif (~8GB)
docker compose exec ollama ollama pull qwen2.5:14b-instruct-q4_K_M

# İndirme durumunu kontrol et
docker compose exec ollama ollama list
```

> ⏱️ İlk indirme 10-30 dakika sürebilir.

---

## 5️⃣ Arayüze Eriş

Tarayıcıda aç:
```
http://<SUNUCU_IP>:3001
```

---

## ✅ Doğrulama

```bash
# Sistem durumu
curl http://localhost:8000/health

# Model listesi
curl http://localhost:11434/api/tags
```

---

## 🛠️ Faydalı Komutlar

```bash
# Logları izle
docker compose logs -f

# Servisleri yeniden başlat
docker compose restart

# Servisleri durdur
docker compose down

# GPU kullanımını izle
nvidia-smi -l 1
```

---

## ⚠️ Sorun Giderme

### "Connection refused" hatası
```bash
# Servislerin durumunu kontrol et
docker compose ps

# Ollama loglarını kontrol et
docker compose logs ollama
```

### Model yüklenmiyor
```bash
# Modeli manuel indir
docker compose exec ollama ollama pull qwen2.5:32b-instruct-q4_K_M
```

### Bellek yetersiz
`.env` dosyasında daha küçük model seç:
```bash
OLLAMA_MODEL=qwen2.5:14b-instruct-q4_K_M
```

---

## 📁 Dosya Yapısı

```
ollama-dgx-spark/
├── docker-compose.yml   # Ana yapılandırma
├── .env                 # Ayarlar
├── backend/             # API kodu
├── frontend/            # Web arayüzü
└── data/                # Şablonlar (kalıcı)
```
