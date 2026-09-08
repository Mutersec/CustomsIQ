# TradeGuard

Ticari uyum motorunuz. GTİP sınıflandırma, ambargo taraması ve gümrük vergisi hesaplama.

## Proje Amaçı

TradeGuard, dış ticaret ve gümrük mevzuatına uyumluluğu sağlayan bir Python kütüphanesidir:

- **GTİP Sınıflandırması**: Gümrük Tarife İstatistik Pozisyonları otomatik taraması
- **Ambargo Taraması**: Yaptırım listeleri ve yasaklı ülke/kuruluş kontrolleri
- **Gümrük Vergisi**: Otomatik tarife hesaplaması ve vergi oranı sorgulama

## Proje Yapısı

```
TradeGuard/
├── src/
│   ├── modules/              # Temel modüller
│   │   ├── gtip_classifier.py
│   │   ├── embargo_screener.py
│   │   └── tariff_calculator.py
│   ├── utils/                # Yardımcı fonksiyonlar
│   │   └── validators.py
│   └── __init__.py
├── tests/
│   ├── unit/                 # Birim testleri
│   ├── integration/          # Entegrasyon testleri
│   └── __init__.py
├── data/
│   ├── customs/              # Gümrük verileri
│   ├── sanctions/            # Yaptırım listeleri
│   └── tariffs/              # Tarife tabloları
├── requirements.txt
├── README.md
└── .gitignore
```

## Kurulum

```bash
pip install -r requirements.txt
```

## Kullanım

```python
from src.modules.gtip_classifier import GTIPClassifier
from src.modules.embargo_screener import EmbargoScreener
from src.modules.tariff_calculator import TariffCalculator

# Örnek
classifier = GTIPClassifier()
result = classifier.classify("ürün_açıklaması")
```

## Geliştirme

Testleri çalıştır:
```bash
pytest
```

Kapsam raporuyla:
```bash
pytest --cov=src
```

## Lisans

MIT
