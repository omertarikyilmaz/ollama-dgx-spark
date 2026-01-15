#!/bin/bash
# MTM AI Hub - GPU Setup Script
# Bu script NVIDIA GPU destegini kontrol eder ve gerekirse kurar

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MTM AI Hub - GPU Kurulum Scripti${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 1. Host'ta nvidia-smi kontrol
echo -e "${YELLOW}[1/5] Host'ta GPU kontrol ediliyor...${NC}"
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}HATA: nvidia-smi bulunamadi!${NC}"
    echo "NVIDIA driver kurulu degil. Once driver'i kurun:"
    echo "  sudo apt install nvidia-driver-535"
    exit 1
fi

nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo -e "${GREEN}GPU bulundu!${NC}"
echo ""

# 2. nvidia-container-toolkit kontrol
echo -e "${YELLOW}[2/5] nvidia-container-toolkit kontrol ediliyor...${NC}"
if ! dpkg -l | grep -q nvidia-container-toolkit; then
    echo -e "${YELLOW}nvidia-container-toolkit kurulu degil, kuruluyor...${NC}"

    # Add NVIDIA repo
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null || true

    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null

    sudo apt-get update -qq
    sudo apt-get install -y -qq nvidia-container-toolkit

    echo -e "${GREEN}nvidia-container-toolkit kuruldu!${NC}"
else
    echo -e "${GREEN}nvidia-container-toolkit zaten kurulu.${NC}"
fi
echo ""

# 3. Docker runtime konfigure et
echo -e "${YELLOW}[3/5] Docker NVIDIA runtime konfigure ediliyor...${NC}"
sudo nvidia-ctk runtime configure --runtime=docker > /dev/null 2>&1
sudo systemctl restart docker
echo -e "${GREEN}Docker konfigure edildi ve yeniden basladi.${NC}"
echo ""

# 4. Docker'da GPU testi
echo -e "${YELLOW}[4/5] Docker'da GPU testi yapiliyor...${NC}"
if docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi > /dev/null 2>&1; then
    echo -e "${GREEN}Docker'da GPU calisiyor!${NC}"
else
    echo -e "${RED}HATA: Docker'da GPU calismiyor!${NC}"
    echo "Lutfen sistemi yeniden baslatin ve tekrar deneyin."
    exit 1
fi
echo ""

# 5. Servisleri baslat
echo -e "${YELLOW}[5/5] MTM AI Hub servisleri baslatiliyor...${NC}"

# Volume'u koru (modeller burada) - ASLA -v kullanma!
OLLAMA_VOLUME=$(docker volume ls -q | grep ollama_data || true)
if [ -n "$OLLAMA_VOLUME" ]; then
    echo -e "${GREEN}Mevcut model volume'u korunuyor: $OLLAMA_VOLUME${NC}"
fi

# Sadece container'lari durdur, volume'lara dokunma
docker compose down 2>/dev/null || true
docker compose up -d

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Kurulum tamamlandi!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Servisler:"
echo "  - Frontend: http://localhost:3001"
echo "  - Backend:  http://localhost:8000"
echo "  - Ollama:   http://localhost:11435"
echo ""
echo "GPU durumunu kontrol et:"
echo "  docker compose exec ollama nvidia-smi"
echo ""
echo "Loglari izle:"
echo "  docker compose logs -f"
