# DGX Spark Notları

## Sunucu Özellikleri
- **İşlemci**: NVIDIA Grace CPU (ARM Neoverse)
- **GPU**: NVIDIA Blackwell (GB10)
- **Bellek**: 128GB Unified Memory
- **Mimari**: ARM64

## Önemli Notlar

### Model Seçimi
- `qwen2.5:32b-instruct-q4_K_M` - Türkçe için en iyi seçim, ~20GB
- `qwen2.5:14b-instruct-q4_K_M` - Daha hızlı, ~8GB
- `llama3.3:70b` - En akıllı ama ~43GB ve daha yavaş

### KV Cache Optimizasyonu
- `q4_0` - En az bellek, en hızlı ama biraz kalite kaybı
- `q8_0` - Dengeli (önerilen)
- `f16` - En yüksek kalite ama daha fazla bellek

### Performans İpuçları
1. `keep_alive` değerini artırarak modeli bellekte tutun
2. `num_parallel` ile paralel işlem sayısını artırın
3. Aynı şablonla çok sayıda haber göndermek KV cache'den faydalanır
