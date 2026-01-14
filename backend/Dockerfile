# NVIDIA NGC PyTorch container - ARM64 + CUDA + Blackwell (sm_121) support
FROM nvcr.io/nvidia/pytorch:25.01-py3

WORKDIR /app

# Install system dependencies
# - Tesseract OCR with Turkish language support
# - FFmpeg for audio processing (Whisper)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-tur \
    tesseract-ocr-eng \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
