<div align="center">

# 🛃 CustomsIQ

### Gümrük ve dış ticaret operasyonları için uyum araç seti
**Eşyayı doğru HS / CN tarife kodunda sınıflandırın ve karşı tarafları yaptırım
listelerine karşı tarayın.**

[![CI](https://github.com/Mutersec/CustomsIQ/actions/workflows/ci.yml/badge.svg)](https://github.com/Mutersec/CustomsIQ/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![Kapsam](https://img.shields.io/badge/kapsam-%9925-brightgreen)
![Testler](https://img.shields.io/badge/testler-40%20ge%C3%A7ti-brightgreen)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Ruff](https://img.shields.io/badge/lint-ruff-261230?logo=ruff&logoColor=white)
![Black](https://img.shields.io/badge/stil-black-000000)
![Mypy](https://img.shields.io/badge/tip%20denetimi-mypy-2A6DB2)
![Lisans](https://img.shields.io/badge/lisans-MIT-green)

**[🌐 Canlı demo](https://customsiq-gs0u.onrender.com/)** · [📖 API referansı](https://customsiq-gs0u.onrender.com/docs)

<sub>Boştayken uykuya geçen ücretsiz bir Render örneğinde barındırılıyor — ilk istek ~30 sn sürebilir.</sub>

[🇬🇧 English](README.md) · **🇹🇷 Türkçe** · [🇩🇪 Deutsch](README.de.md)

</div>

---

## 📑 İçindekiler

| | | |
|---|---|---|
| [🎯 Problem](#-problem) | [✨ Özellikler](#-özellikler) | [🏗️ Mimari](#️-mimari) |
| [🧠 Tasarım kararları](#-tasarım-kararları) | [⚙️ Kurulum](#️-kurulum) | [🚀 Kullanım](#-kullanım) |
| [🌐 API referansı](#-api-referansı) | [🧪 Kalite ve testler](#-kalite-ve-testler) | [📦 Örnek veri](#-örnek-veri) |
| [🗺️ Yol haritası](#️-yol-haritası) | [📁 Proje yapısı](#-proje-yapısı) | [📄 Lisans](#-lisans) |

---

## 🎯 Problem

Doğru **CN kodunu** (AB *Kombine Nomanklatür*'ü; uluslararası HS kodunu 8 haneye, TARIC'te ise
10 haneye genişletir) belirlemek, gümrük beyannamesi sürecinin en yavaş ve hataya en açık
adımlarından biridir. Bugün bu işlem, on binlerce satırlık tarife cetveli üzerinde elle
yapılmaktadır.

| Sorun | Ticari sonucu |
|---|---|
| 🔍 Devasa tarife cetvelinde elle arama | Beyan süreci yavaşlar; sonuç, o vardiyadaki operatöre göre değişir |
| ❌ Yanlış sınıflandırma | Hatalı vergi oranı, cezalar, gümrükte bekleyen sevkiyatlar |
| 🧠 Bilginin kişilere bağlı kalması | Yeni personelin adaptasyonu yavaşlar; seçilen kodun denetlenebilir gerekçesi olmaz |

**CustomsIQ ilk eleme adımını otomatikleştirir:** sade bir ürün açıklaması verirsiniz, benzerlik
skoruyla sıralanmış kısa bir tarife kodu listesi alırsınız — bu, uzmanın onaylayacağı bir başlangıç
noktasıdır; tek başına karar veren bir kara kutu değildir.

---

## ✨ Özellikler

| | Özellik | Açıklama |
|---|---|---|
| 🔍 | **Bulanık arama** | Serbest metin açıklama → benzerlik skoruna göre sıralanmış CN/TARIC kodları |
| 🚫 | **Yaptırım taraması** | İsim → kelime sırasına ve kısmi isimlere toleranslı yasaklı taraf eşleşmeleri |
| 🖥️ | **Web arayüzü** | `/` adresinde sunulan tek sayfalık arayüz — derleme adımı, framework veya CDN yok |
| 💻 | **Etkileşimli CLI** | Aynı komut satırından kod araması veya `screen <isim>` taraması |
| 🌐 | **REST API** | FastAPI üzerinde `GET /search` ve `GET /screen`, otomatik `/docs` arayüzü |
| 🗄️ | **Kurulum gerektirmeyen depolama** | Standart kütüphanedeki SQLite; 20 kod + 18 kurgusal kayıtla gelir |
| ⚙️ | **Ortam tabanlı yapılandırma** | `pydantic-settings` `.env` dosyasını okur — sabit kodlanmış yol veya eşik yok |
| 🚨 | **Tipli hatalar** | `InvalidQueryError`, `HSCodeNotFoundError` → temiz HTTP `400` / `404` semantiği |
| 🧪 | **Zorunlu kalite** | ruff + black + mypy + %98 kapsam; her push'ta CI tarafından denetlenir |

---

## 🏗️ Mimari

İki yetenek — **CN kodu araması** ve **yaptırım taraması** — ortak tek bir eşleştirme katmanı
üzerinde durur. CLI ve HTTP API, `search()` ve `screen_entity()` fonksiyonlarının ince birer
adaptörüdür; skorlama ve doğrulama mantığı tam olarak tek bir yerde bulunur, asla tekrarlanmaz.

```mermaid
flowchart LR
    subgraph Arayuzler["Arayüzler"]
        CLI["💻 main.py<br/>Etkileşimli CLI"]
        API["🌐 api.py<br/>FastAPI /search · /screen"]
    end

    SEARCH["🔍 search.py<br/>CN kodu sıralama"]
    SCREEN["🚫 embargo_screener.py<br/>yaptırım eşleşmeleri"]
    MATCH["🧩 matching.py<br/>doğrulama + benzerlik"]
    DB[("🗄️ database.py<br/>SQLite · hs_codes<br/>· sanctioned_entities")]
    EXC["🚨 exceptions.py"]
    CFG["⚙️ config.py<br/>.env"]

    CLI --> SEARCH
    CLI --> SCREEN
    API --> SEARCH
    API --> SCREEN
    SEARCH --> MATCH
    SCREEN --> MATCH
    SEARCH --> DB
    SCREEN --> DB
    MATCH -. hata fırlatır .-> EXC
    DB -. hata fırlatır .-> EXC
    CFG --> CLI
    CFG --> API
    CFG --> SCREEN
```

### Modül sorumlulukları

| Modül | Sorumluluk |
|---|---|
| `models.py` | `HSCode` ve `SanctionedEntity` — değişmez kayıtlar |
| `database.py` | SQLite şeması, bağlantı, örnek veri, `fetch_all*()`, `get_by_code()` |
| `matching.py` | Girdi doğrulama + benzerlik skorlaması (**her iki yetenek de bunu kullanır**) |
| `search.py` | CN kodlarını açıklama benzerliğine göre sıralar |
| `embargo_screener.py` | Yaptırım listesi eşleşmelerini isim benzerliğine göre sıralar |
| `exceptions.py` | `CustomsIQError` → `InvalidQueryError`, `HSCodeNotFoundError` |
| `config.py` | `pydantic-settings`; `CUSTOMSIQ_*` ortam değişkenlerini ve `.env` dosyasını okur |
| `logging_config.py` | Ortak loglama kurulumu — stdout'a sade format, hiçbir yerde `print()` yok |
| `main.py` | Etkileşimli CLI giriş noktası (arama + `screen <isim>`) |
| `api.py` | FastAPI uygulaması: `/` adresinde arayüzü sunar, ayrıca `/search`, `/screen`, `/health` |
| `static/index.html` | Web arayüzünün tamamı — satır içi CSS, saf `fetch()`, sıfır bağımlılık |

### Veri modeli

```sql
CREATE TABLE hs_codes (
    code        TEXT PRIMARY KEY,   -- örn. "6109100000"
    description TEXT NOT NULL,      -- örn. "Cotton T-shirts, knitted"
    category    TEXT NOT NULL       -- örn. "Textile"
);

CREATE TABLE sanctioned_entities (
    name        TEXT PRIMARY KEY,   -- örn. "Northwind Maritime Holdings Ltd"
    country     TEXT NOT NULL,      -- ISO 3166-1 alpha-2, örn. "CY"
    list_source TEXT NOT NULL,      -- örn. "EU Consolidated Financial Sanctions List"
    date_added  TEXT NOT NULL       -- ISO 8601 tarih, örn. "2023-04-12"
);
```

---

## 🧠 Tasarım kararları

### Neden `rapidfuzz` / `thefuzz` yerine `difflib`?

`difflib.SequenceMatcher` Python ile birlikte gelir. Bu da **sıfır ek bağımlılık**, sürüm sabitleme
veya güvenlik denetimi derdi olmayan bir kurulum demektir — üstelik mevcut veri ölçeğinde fazlasıyla
yeterlidir.

| | `difflib` *(seçilen)* | `rapidfuzz` |
|---|---|---|
| **Bağımlılık** | ✅ Standart kütüphane | ⚠️ Üçüncü parti + C eklentisi |
| **~10² satırda hız** | ✅ Fark edilmez | ✅ Fark edilmez |
| **~10⁵ satırda hız** | ❌ Belirgin şekilde yavaş | ✅ C ile optimize, çok daha hızlı |
| **Kelime sırasına toleransı** | ❌ Yalnızca konumsal eşleştirme | ✅ `token_sort` / `token_set` skorlayıcıları |
| **Toplu işlem kapasitesi** | ❌ Saf Python | ✅ `process.extract`, çok çekirdekli |

### 🔀 Ne zaman geçilmeli

Aşağıdakilerden **herhangi biri** gerçekleştiğinde `matching.py` içindeki `similarity()` fonksiyonunu
`rapidfuzz.fuzz.WRatio` ile değiştirin:

1. **📈 Ölçek** — gerçek tarife cetveli (on binlerce satır) doğrusal taramayı ölçülebilir biçimde yavaşlattığında.
2. **🔤 Kelime sırası** — *"pantolon pamuklu erkek"* gibi sorguların *"Men's cotton trousers"* ile eşleşmesi gerektiğinde; konumsal eşleştirme bunu iyi yapamaz.
3. **⚡ İşlem hacmi** — toplu yeniden sınıflandırma işi saniyede binlerce sorgu gerektirdiğinde.

> Değişiklik **tek bir fonksiyonla** sınırlıdır; dolayısıyla bu, sonraya bırakılabilecek ucuz bir
> karardır — bugün verilmesi gereken bir tasarım taahhüdü değil.

### Diğer bilinçli tercihler

| Karar | Gerekçe | Yükseltme yolu |
|---|---|---|
| **Postgres değil SQLite** | Tek düğümlü, ağırlıklı okuma yapılan referans verisi; sıfır operasyon yükü | Çoklu yazar eşzamanlılığı gerektiğinde bağlantı katmanı değiştirilir |
| **`check_same_thread=False` ile tek paylaşımlı bağlantı** | Basit; FastAPI'nin thread havuzuyla çalışır | Eşzamanlı yazmalar ortaya çıktığında bağlantı havuzu |
| **`print()` değil loglama** | CLI ve API için aynı çıktı yolu; seviye yapılandırmayla kontrol edilir | — |
| **Doğrulamanın `matching.py` içinde olması** | Arama, tarama, CLI ve API bunu devralır; yeni bir çağıran eklenerek atlanması imkânsızdır | — |
| **`EmbargoScreeningError` eklenmemesi** | Taramanın girdi doğrulaması aramanınkiyle birebir aynı; yeni sınıf yerine `InvalidQueryError` yeniden kullanılır | Tarama gerçekten farklı bir hata durumu kazanırsa eklenir |

### 🚫 İsim eşleştirmesi, ürün eşleştirmesi değildir

Yaptırım taraması tutarlılık ve sıfır bağımlılık için aynı `difflib` çekirdeğini kullanır; ancak
isimler, düz orana ek olarak iki sinyal daha gerektirdi. Demo liste üzerinde ölçülen değerler:

| Sorgu ↔ listedeki isim | düz | token-sıralı | token örtüşmesi |
|---|---|---|---|
| `John Smith` ↔ `Smith, John` | 0.50 ❌ | **1.00** ✅ | 1.00 |
| `Northwind Maritime` ↔ `Northwind Maritime Holdings Ltd` | 0.73 ❌ | 0.73 ❌ | **1.00** ✅ |
| `Smith` ↔ `John Smith` | 0.67 | 0.67 | 1.00 ⚠️ |

Kelime sırası varyantları **token sıralaması**, kısmi şirket isimleri ise **token örtüşmesi**
gerektirir: 0.75 eşiğinde diğer iki sinyal 2. satırı tamamen kaçırır. Örtüşme terimi yalnızca kısa
ismin ≥ 2 kelimesi olduğunda dikkate alınır; aksi hâlde tek başına bir soyadı (3. satır) o soyadını
içeren her kaydı yakalardı. Tarama, geçerli sinyallerin en yükseğini alır ve bilinçli olarak
kapsayıcıdır: bir yanlış negatif yaptırımlı tarafın geçmesine yol açar, yanlış pozitif ise uzmana
yalnızca bir bakışa mal olur.

**`rapidfuzz`'a geçişi ilk gerektirecek olan da ürün araması değil, budur.** Bu iki sinyal aslında
`rapidfuzz`'un `token_sort_ratio` ve `token_set_ratio` fonksiyonlarının elle yazılmış hâlidir; ayrıca
`partial_ratio` ve çok daha hızlı tarama sunar. Gerçek AB Konsolide Mali Yaptırımlar Listesi binlerce
kayıt içerir, her taramada baştan taranır ve `difflib`'in karşılığı olmayan takma ad ile
transliterasyon desteği gerektirir.

### 🇪🇺 AB uyumu

> Veri modeli ve terminoloji, hedef pazarı (AB merkezli ticaret uyum rolleri) yansıtacak şekilde AB
> Kombine Nomanklatürü ve AB ticaret uyum çerçeveleriyle hizalanmıştır.

Somut olarak bu şu anlama gelir:

| Konu | Doğruluk kaynağı |
|---|---|
| Tarife kodları ve nomanklatür | [AB TARIC veritabanı](https://ec.europa.eu/taxation_customs/dds2/taric) — CN-8 kodları, AB alt açılımlarıyla TARIC-10 |
| Yaptırım ve ambargo taraması | AB Konsolide Mali Yaptırımlar Listesi |
| Tercihli vergi oranları | AB ticaret anlaşmaları |

---

## ⚙️ Kurulum

```bash
# 1. Depoyu klonlayın
git clone https://github.com/Mutersec/CustomsIQ.git
cd CustomsIQ

# 2. Sanal ortam
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Bağımlılıklar
pip install -r requirements.txt

# 4. (İsteğe bağlı) yapılandırma
cp .env.example .env
```

### Yapılandırma

Tüm ayarlar ortam değişkenlerinden veya `.env` dosyasından okunur:

| Değişken | Varsayılan | Açıklama |
|---|---|---|
| `CUSTOMSIQ_DATABASE_PATH` | `customsiq.db` | SQLite dosya yolu (geçici veritabanı için `:memory:`) |
| `CUSTOMSIQ_LOG_LEVEL` | `INFO` | Python log seviyesi (`DEBUG`, `INFO`, `WARNING`, …) |
| `CUSTOMSIQ_SCREENING_THRESHOLD` | `0.75` | Tarama eşleşmesi için asgari isim benzerlik skoru (0–1) |

---

## 🚀 Kullanım

### 💻 Etkileşimli CLI

```bash
python -m src.customsiq.main
```

```text
seeded 20 rows into hs_codes
seeded 18 rows into sanctioned_entities
CustomsIQ (type 'quit' to exit)
Enter a product description to search CN codes,
or 'screen <name>' to run a sanctions check.

> cotton t-shirt
1. 6109100000  (74%)  Cotton T-shirts, knitted        [Textile]
2. 6203420000  (57%)  Men's cotton trousers           [Textile]
3. 6204620000  (54%)  Women's cotton trousers         [Textile]
4. 6110200000  (42%)  Cotton pullovers and sweaters   [Textile]
5. 8528721000  (35%)  Color television receivers      [Electronics]

> screen Northwind Maritime
1 potential sanctions match(es) for 'Northwind Maritime':
1. Northwind Maritime Holdings Ltd  (100%)  [CY]  EU Consolidated Financial Sanctions List  listed 2023-04-12

> screen Quokka Beachwear
No sanctions match for 'Quokka Beachwear'.
```

### 🖥️ Web arayüzü

```bash
uvicorn src.customsiq.api:app --reload
```

Web arayüzü için **http://localhost:8000/** adresini açın — her iki yetenek tek sayfada; ya da
[canlı demoyu](https://customsiq-gs0u.onrender.com/) deneyin.

### 🌐 REST API

Aynı sunucu JSON API'yi de sunar:

Ardından etkileşimli Swagger arayüzü için **http://localhost:8000/docs** adresini açın.

```bash
curl "http://localhost:8000/search?q=cotton+t-shirt&limit=2"
```

```json
[
  {
    "code": "6109100000",
    "description": "Cotton T-shirts, knitted",
    "category": "Textile",
    "score": 0.7368421052631579
  },
  {
    "code": "6203420000",
    "description": "Men's cotton trousers",
    "category": "Textile",
    "score": 0.5714285714285714
  }
]
```

### 🐍 Kütüphane olarak

```python
from src.customsiq.database import get_connection, seed
from src.customsiq.search import search

conn = get_connection("customsiq.db")
seed(conn)

for result in search(conn, "lithium battery", limit=3):
    print(f"{result.hs_code.code}  {result.score:.0%}  {result.hs_code.description}")
```

---

## 🌐 API referansı

| Metot | Uç nokta | Açıklama |
|---|---|---|
| `GET` | `/` | **Web arayüzü** (HTML sayfa) |
| `GET` | `/health` | Canlılık kontrolü — `{"service": "CustomsIQ API", "docs": "/docs", "status": "running"}` |
| `GET` | `/search` | Ürün açıklaması için sıralanmış CN kodu eşleşmeleri |
| `GET` | `/screen` | Kişi veya kuruluş ismi için yaptırım listesi eşleşmeleri |
| `GET` | `/docs` | Etkileşimli Swagger arayüzü (otomatik üretilir) |

**`GET /search` parametreleri**

| Parametre | Tip | Varsayılan | Kısıtlar | Açıklama |
|---|---|---|---|---|
| `q` | `str` | *zorunlu* | 1–500 karakter, boş olamaz | Serbest metin ürün açıklaması |
| `limit` | `int` | `5` | 1–50 | Azami sonuç sayısı |

**`GET /screen` parametreleri**

| Parametre | Tip | Varsayılan | Kısıtlar | Açıklama |
|---|---|---|---|---|
| `name` | `str` | *zorunlu* | 1–500 karakter, boş olamaz | Taranacak kişi veya kuruluş ismi |

Tarama `limit` almaz: eşiğin üzerindeki her eşleşme döndürülür; sessizce kırpılmış bir eşleşme
listesi, kötü bir sıralamadan öte bir uyum ihlali olurdu.

```bash
curl "http://localhost:8000/screen?name=Northwind+Maritime"
```

```json
[
  {
    "name": "Northwind Maritime Holdings Ltd",
    "country": "CY",
    "list_source": "EU Consolidated Financial Sanctions List",
    "date_added": "2023-04-12",
    "score": 1.0
  }
]
```

**Durum kodları**

| Kod | Anlamı |
|---|---|
| `200` | Başarılı — eşleşme dizisi (boş olabilir) |
| `400` | `InvalidQueryError` — boş sorgu veya 500 karakterden uzun |
| `422` | Eksik/geçersiz parametre tipi (FastAPI doğrulaması) |

---

## 🧪 Kalite ve testler

Her push ve pull request'te tüm kalite kapısı [GitHub Actions](.github/workflows/ci.yml) üzerinde çalışır:

```mermaid
flowchart LR
    A["📥 Checkout"] --> B["🐍 Python 3.11"] --> C["📦 Kurulum"]
    C --> D["🔎 ruff"] --> E["🎨 black --check"] --> F["🏷️ mypy"] --> G["🧪 pytest ≥%80"]
```

```bash
ruff check .                                                  # lint
black .                                                       # biçimlendirme
mypy src                                                      # tip denetimi
pytest --cov --cov-report=term-missing --cov-fail-under=80    # testler + kapsam eşiği
```

### Güncel test kapsamı

| Modül | Kapsam |
|---|---|
| `api.py` · `config.py` · `database.py` · `embargo_screener.py` · `matching.py` | 🟢 %100 |
| `exceptions.py` · `logging_config.py` · `models.py` · `search.py` | 🟢 %100 |
| `main.py` | 🟢 %93 |
| **Toplam** | **🟢 %99** (40 test, eşik %80) |

### Test edilen uç durumlar

| Durum | Beklenen davranış |
|---|---|
| Boş / yalnızca boşluktan oluşan sorgu veya isim | `InvalidQueryError` → HTTP `400` |
| 500 karakterden uzun sorgu | `InvalidQueryError` → HTTP `400` |
| SQL injection biçimli girdi (`'; DROP TABLE hs_codes; --`) | Parametreli sorgularla güvenle işlenir; tablo bozulmaz |
| Emoji ve ASCII dışı girdi (`📱 Handy-Ladegerät`, `Ünal Çelik A.Ş.`) | Normal şekilde skorlanır, çökme olmaz |
| Ters kelime sıralı isim (`Aleksandr Voronin-Teske`) | Soyadı önce yazılmış liste kaydıyla eşleşir |
| Kısmi şirket ismi (`Northwind Maritime`) | Listedeki tam isimle eşleşir |
| Listede karşılığı olmayan isim | Hata değil, boş sonuç |
| Bilinmeyen kodun birebir sorgulanması | `HSCodeNotFoundError` |
| Dolu veritabanının yeniden doldurulması | Idempotent — iki tabloda da mükerrer kayıt oluşmaz |

---

## 📦 Örnek veri

Veritabanı, AB Kombine Nomanklatür biçiminde yazılmış **8 kategoriye yayılmış 20 temsili CN/TARIC
koduyla** doldurulur:

| Kategori | Kod sayısı |
|---|---|
| 📱 Elektronik | 5 |
| 👕 Tekstil | 5 |
| 🍫 Gıda | 5 |
| 💊 İlaç · 🚗 Otomotiv · 🪑 Mobilya · 🧴 Plastik · 🔩 Metal | her biri 1 |

<details>
<summary><b>20 kaydın tamamını göster</b></summary>

| CN/TARIC kodu | Açıklama | Kategori |
|---|---|---|
| `8517120000` | Cep telefonları ve akıllı telefonlar | Elektronik |
| `8471300000` | Taşınabilir otomatik bilgi işlem makineleri (dizüstü) | Elektronik |
| `8528721000` | Renkli televizyon alıcıları | Elektronik |
| `8544421000` | USB kabloları ve veri kabloları | Elektronik |
| `8507600000` | Lityum iyon piller | Elektronik |
| `6109100000` | Pamuklu tişörtler, örme | Tekstil |
| `6203420000` | Erkek pamuklu pantolonlar | Tekstil |
| `6204620000` | Kadın pamuklu pantolonlar | Tekstil |
| `6110200000` | Pamuklu kazak ve süveterler | Tekstil |
| `6402990000` | Kauçuk veya plastik tabanlı ayakkabılar | Tekstil |
| `0901210000` | Kavrulmuş kahve, kafeini alınmamış | Gıda |
| `1806320000` | Çikolata blokları, dolgusuz | Gıda |
| `2009110000` | Dondurulmuş portakal suyu | Gıda |
| `0406100000` | Taze peynir | Gıda |
| `1905310000` | Tatlı bisküviler | Gıda |
| `3004900000` | Tedavi amaçlı ilaçlar | İlaç |
| `4011100000` | Otomobiller için yeni dış lastikler | Otomotiv |
| `9403300000` | Ahşap büro mobilyaları | Mobilya |
| `3926909700` | Plastik ev eşyaları | Plastik |
| `7326909800` | Demir veya çelikten muhtelif eşya | Metal |

</details>

> ⚠️ Bu veriler geliştirme ve test amaçlı **demo verilerdir**. Üretim kullanımı için
> [AB TARIC veritabanındaki](https://ec.europa.eu/taxation_customs/dds2/taric) resmî nomanklatür
> gereklidir.

### Yaptırım listesi

`sanctioned_entities` tablosu, AB Konsolide Mali Yaptırımlar Listesi kayıtları tarzında **18 kayıtla**
doldurulur: uydurma ticaret, denizcilik ve mühendislik şirketleri ile gerçek listelerin yayımlama
biçimine uygun olarak soyadı önce yazılmış birkaç sentetik kişi ismi.

| Alan | Örnek |
|---|---|
| `name` | `Northwind Maritime Holdings Ltd` · `Voronin-Teske, Aleksandr` |
| `country` | `CY`, `AE`, `DE`, `RS`, `MT`, `NL`, … |
| `list_source` | `EU Consolidated Financial Sanctions List` · `EU Dual-Use Export Control Watchlist` |
| `date_added` | `2023-04-12` |

> 🚨 **Bu listedeki her isim kurgusaldır.** Hiçbiri gerçek bir yaptırımlı kişi veya kuruluşa karşılık
> gelmez ve liste asla gerçek tarama için kullanılmamalıdır. Üretim taraması, resmî AB Konsolide Mali
> Yaptırımlar Listesi'ni gerektirir.

---

## 🗺️ Yol haritası

CN kodu araması ve yaptırım taraması bugün kullanıma hazırdır. İki uyum modülü iskelet hâlinde
kalmaya devam ediyor — gerçek bir mantık içermedikleri sürece kapsam eşiğinin dışında tutulurlar:

| Modül | Durum | Kapsam |
|---|---|---|
| `search.py` + `api.py` | ✅ **Tamamlandı** | CLI ve REST üzerinden bulanık CN kodu araması |
| `embargo_screener.py` | ✅ **Tamamlandı** | CLI ve REST üzerinden yasaklı taraf isim taraması |
| `cn_classifier.py` | 🚧 İskelet | AB TARIC veri kümesine karşı kural ve güven skoru tabanlı sınıflandırma |
| `tariff_calculator.py` | 🚧 İskelet | Vergi hesaplama, menşe kuralları, AB tercihli ticaret anlaşması oranları |

Tarama için planlanan genişlemeler: ülke düzeyinde ambargo kontrolleri, ürün/varış yeri kısıtları ve
kuruluş isimleri için takma ad ile transliterasyon desteği.

---

## 📁 Proje yapısı

```text
CustomsIQ/
├── .github/workflows/ci.yml     # ruff → black → mypy → pytest
├── src/
│   ├── customsiq/
│   │   ├── models.py            # HSCode + SanctionedEntity kayıtları
│   │   ├── database.py          # SQLite katmanı + örnek veri (iki tablo)
│   │   ├── matching.py          # ortak doğrulama + benzerlik skorlaması
│   │   ├── search.py            # CN kodu sıralaması
│   │   ├── embargo_screener.py  # yaptırım isim taraması
│   │   ├── exceptions.py        # tipli hata hiyerarşisi
│   │   ├── config.py            # pydantic-settings / .env
│   │   ├── logging_config.py    # ortak loglama kurulumu
│   │   ├── main.py              # CLI giriş noktası
│   │   ├── api.py               # FastAPI uygulaması (arayüzü de sunar)
│   │   ├── static/index.html    # web arayüzü — tek dosya, derleme adımı yok
│   │   ├── cn_classifier.py     # 🚧 iskelet
│   │   └── tariff_calculator.py # 🚧 iskelet
│   └── utils/validators.py      # CN/TARIC format ve ülke kodu doğrulaması
├── tests/                       # 40 test — birim, API, CLI, tarama, uç durumlar
├── pyproject.toml               # ruff · black · mypy · pytest · coverage
├── requirements.txt
└── .env.example
```

---

## 📄 Lisans

**MIT Lisansı** ile yayımlanmıştır.

<div align="center">

[🇬🇧 English](README.md) · **🇹🇷 Türkçe** · [🇩🇪 Deutsch](README.de.md)

</div>
