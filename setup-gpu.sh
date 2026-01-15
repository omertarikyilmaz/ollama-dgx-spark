#!/bin/bash
# MTM AI Hub - GPU Setup Script
# Bu script NVIDIA GPU destegini kontrol eder ve gerekirse kurar
# ARM64 (Grace Blackwell / DGX Spark / ASUS Ascent GX10) destekli

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  MTM AI Hub - GPU Kurulum Scripti${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Arsitektur tespit
ARCH=$(uname -m)
echo -e "${BLUE}Sistem: $ARCH${NC}"

# DGX OS / Grace Blackwell tespiti
IS_DGX=false
if [ -f /etc/dgx-release ] || grep -qi "dgx\|grace\|blackwell" /proc/cpuinfo 2>/dev/null || [ "$ARCH" = "aarch64" ]; then
    IS_DGX=true
    echo -e "${BLUE}DGX/Grace Blackwell sistem tespit edildi${NC}"
fi
echo ""

# 1. Host'ta nvidia-smi kontrol
echo -e "${YELLOW}[1/5] Host'ta GPU kontrol ediliyor...${NC}"
if ! command -v nvidia-smi &> /dev/null; then
    echo -e "${RED}HATA: nvidia-smi bulunamadi!${NC}"
    echo "NVIDIA driver kurulu degil."
    if [ "$IS_DGX" = true ]; then
        echo "DGX OS'ta driver onceden kurulu olmali. Sistem yoneticinize dansin."
    else
        echo "Driver kurmak icin: sudo apt install nvidia-driver-535"
    fi
    exit 1
fi

nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo -e "${GREEN}GPU bulundu!${NC}"
echo ""

# 2. nvidia-container-toolkit kontrol
echo -e "${YELLOW}[2/5] nvidia-container-toolkit kontrol ediliyor...${NC}"

# DGX OS genellikle onceden konfigureli gelir
if [ "$IS_DGX" = true ]; then
    if command -v nvidia-ctk &> /dev/null; then
        echo -e "${GREEN}nvidia-container-toolkit zaten kurulu (DGX OS).${NC}"
    else
        echo -e "${YELLOW}nvidia-container-toolkit kuruluyor (ARM64)...${NC}"
        # ARM64 icin NVIDIA repo
        curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null || true

        distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
        curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
            sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
            sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null

        sudo apt-get update -qq
        sudo apt-get install -y -qq nvidia-container-toolkit
    fi
else
    if ! dpkg -l | grep -q nvidia-container-toolkit; then
        echo -e "${YELLOW}nvidia-container-toolkit kurulu degil, kuruluyor...${NC}"
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
fi
echo ""

# 3. Docker runtime konfigure et
echo -e "${YELLOW}[3/5] Docker NVIDIA runtime konfigure ediliyor...${NC}"
if command -v nvidia-ctk &> /dev/null; then
    sudo nvidia-ctk runtime configure --runtime=docker > /dev/null 2>&1 || true
fi
sudo systemctl restart docker 2>/dev/null || sudo service docker restart 2>/dev/null || true
echo -e "${GREEN}Docker konfigure edildi.${NC}"
echo ""

# 4. Docker'da GPU testi
echo -e "${YELLOW}[4/5] Docker'da GPU testi yapiliyor...${NC}"

# Arsitekture gore test image sec
if [ "$ARCH" = "aarch64" ]; then
    # ARM64 icin - basit test, cuda image yerine dogrudan nvidia-smi
    echo -e "${BLUE}ARM64 testi: docker --gpus ile nvidia-smi${NC}"
    if docker run --rm --gpus all ubuntu:22.04 nvidia-smi > /dev/null 2>&1; then
        echo -e "${GREEN}Docker'da GPU calisiyor! (ARM64)${NC}"
    else
        # Alternatif: ollama image ile test
        echo -e "${YELLOW}Basit test basarisiz, ollama image ile deneniyor...${NC}"
        if docker run --rm --gpus all ollama/ollama:latest nvidia-smi > /dev/null 2>&1; then
            echo -e "${GREEN}Docker'da GPU calisiyor! (ollama image)${NC}"
        else
            echo -e "${YELLOW}UYARI: GPU testi basarisiz ama devam ediliyor...${NC}"
            echo "DGX/Grace sistemlerinde Docker GPU erisimi farkli calisabilir."
            echo "Ollama kendi GPU erisimini yonetebilir."
        fi
    fi
else
    # x86_64 icin standart test
    if docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi > /dev/null 2>&1; then
        echo -e "${GREEN}Docker'da GPU calisiyor!${NC}"
    else
        echo -e "${RED}HATA: Docker'da GPU calismiyor!${NC}"
        echo "nvidia-container-toolkit kurulumunu kontrol edin."
        exit 1
    fi
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
