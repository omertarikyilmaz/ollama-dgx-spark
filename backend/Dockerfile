FROM python:3.12-slim

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
    git \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch Nightly with CUDA 12.8 (Blackwell sm_120/121 support)
RUN pip install --pre torch torchaudio --index-url https://download.pytorch.org/whl/nightly/cu128

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
