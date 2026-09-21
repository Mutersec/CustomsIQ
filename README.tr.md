<div align="center">

# 🛃 CustomsIQ

### Gümrük ve dış ticaret operasyonları için uyum araç seti
**Eşyayı doğru HS / CN tarife kodunda sınıflandırın, karşı tarafları yaptırım listelerine karşı
tarayın ve ödenecek vergiyi hesaplayın.**

[![CI](https://github.com/Mutersec/CustomsIQ/actions/workflows/ci.yml/badge.svg)](https://github.com/Mutersec/CustomsIQ/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![Kapsam](https://img.shields.io/badge/kapsam-%9825-brightgreen)
![Testler](https://img.shields.io/badge/testler-197%20ge%C3%A7ti-brightgreen)
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

> **ℹ️ Demo veri kümesi hakkında.** Canlı demo, Render'ın ücretsiz katmanında hızlı soğuk başlangıç
> için küçük ve seçilmiş bir veri kümesiyle (20 HS kodu) çalışır; o katmanda dosya sistemi
> hareketsizlikte sıfırlanır. İçe aktarma hattı, gerçekçi CN formatındaki veriye karşı uçtan uca
> doğrulanmıştır (aşağıdaki
> [Gerçek CN nomanklatürünü içe aktarma](#gerçek-cn-nomanklatürünü-içe-aktarma) bölümüne bakın) —
> hattı yerelde tam AB veri kümesiyle ya da kalıcı diskli bir dağıtımda çalıştırmak, canlı demonun
> kullandığı şemanın aynısını doldurur.

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
| 🧠 | **Kod sınıflandırma** | Güven skoru ve her öneriyi getiren terimlerle TF-IDF önerileri |
| 🚫 | **Yaptırım taraması** | İsim → kelime sırasına ve kısmi isimlere toleranslı yasaklı taraf eşleşmeleri |
| 💶 | **Vergi hesaplama** | Kod + menşe + kıymet → ödenecek vergi, uygulanan oran ve gerekçesiyle |
| 📋 | **İnsan onayı / denetim izi** | Sınıflandırma, tarama veya vergi sonucunu onayla/reddet/işaretle — sadece ekleme yapılır |
| 🕘 | **Sürümlü CN kodları (SCD Type 2)** | Değişen her açıklama/kategori eski değerini zaman damgasıyla korur — `GET /codes/{code}/history` |
| 📊 | **Analitik gösterge paneli** | Referans veriler, inceleme faaliyeti ve içe aktarma çalıştırmalarının salt-okunur özeti — `GET /dashboard/stats` |
| ⚠️ | **Toplu risk skorlama** | Sınıflandırma güveni, tarama ve vergiyi birleştiren tek açıklanabilir skor — `GET /assess-risk` |
| 🖥️ | **Web arayüzü** | `/` adresinde sunulan tek sayfalık arayüz — derleme adımı, framework veya CDN yok |
| 📥 | **Gerçek veri içe aktarma** | Resmî AB CN nomanklatürünü yerel dosyadan yükler, değişiklikleri sürümleyerek |
| 💻 | **Etkileşimli CLI** | Aynı komut satırından kod araması veya `screen <isim>` taraması |
| 🌐 | **REST API** | FastAPI üzerinde `GET /search` ve `GET /screen`, otomatik `/docs` arayüzü |
| 🗄️ | **Kurulum gerektirmeyen depolama** | Standart kütüphanedeki SQLite; 20 kod + 18 kurgusal kayıtla gelir |
| 🐘 | **Çift veritabanı desteği** | Aynı SQL PostgreSQL üzerinde de çalışır — tek bir ortam değişkeniyle açılır, varsayılan SQLite kalır |
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
        API["🌐 api.py<br/>FastAPI /search · /classify<br/>· /screen · /calculate-duty · /review<br/>· /codes/{code}/history · /dashboard/stats<br/>· /assess-risk"]
        IMPORT["📥 import_cn_codes.py<br/>CLI içe aktarma aracı"]
    end

    SEARCH["🔍 search.py<br/>CN kodu sıralama"]
    CLS["🧠 cn_classifier.py<br/>TF-IDF + gerekçe"]
    SCREEN["🚫 embargo_screener.py<br/>yaptırım eşleşmeleri"]
    DUTY["💶 tariff_calculator.py<br/>oran seçimi + hesap"]
    REVIEW["📋 review.py<br/>karar kaydet + listele"]
    DASH["📊 dashboard.py<br/>toplu istatistik"]
    RISK["⚠️ risk.py<br/>toplu değerlendirme"]
    MATCH["🧩 matching.py<br/>doğrulama + benzerlik"]
    DB[("🗄️ database.py<br/>SQLite · hs_codes · sanctioned_entities<br/>· tariff_rates · review_decisions<br/>· hs_code_history · cn_code_versions")]
    EXC["🚨 exceptions.py"]
    CFG["⚙️ config.py<br/>.env"]

    CLI --> SEARCH
    CLI --> CLS
    CLI --> SCREEN
    CLI --> DUTY
    CLI --> REVIEW
    CLI --> RISK
    API --> SEARCH
    API --> CLS
    API --> SCREEN
    API --> DUTY
    API --> REVIEW
    API --> DASH
    API --> RISK
    API --> DB
    IMPORT --> DB
    DASH --> DB
    RISK --> CLS
    RISK --> SCREEN
    RISK --> DUTY
    SEARCH --> MATCH
    CLS --> MATCH
    SCREEN --> MATCH
    SEARCH --> DB
    CLS --> DB
    SCREEN --> DB
    DUTY --> DB
    REVIEW --> DB
    DUTY -. hata fırlatır .-> EXC
    MATCH -. hata fırlatır .-> EXC
    DB -. hata fırlatır .-> EXC
    REVIEW -. hata fırlatır .-> EXC
    CFG --> CLI
    CFG --> API
    CFG --> SCREEN
```

### Modül sorumlulukları

| Modül | Sorumluluk |
|---|---|
| `models.py` | `HSCode`, `SanctionedEntity`, `TariffRate`, `ReviewDecision`, `HSCodeVersion` ve `ImportRun` — değişmez kayıtlar |
| `database.py` | SQLite şeması, bağlantı, örnek veri, `fetch_all*()`, `get_by_code()`, `upsert_hs_codes_with_history()` (SCD Type 2) |
| `matching.py` | Girdi doğrulama + benzerlik skorlaması (**her iki yetenek de bunu kullanır**) |
| `search.py` | CN kodlarını açıklama benzerliğine göre sıralar |
| `cn_classifier.py` | TF-IDF terim ağırlığıyla kod önerir ve eşleşen terimleri bildirir |
| `embargo_screener.py` | Yaptırım listesi eşleşmelerini isim benzerliğine göre sıralar |
| `tariff_calculator.py` | Uygulanacak vergi oranını seçer ve ödenecek tutarı hesaplar |
| `review.py` | Geçmiş kararlar üzerinde insan onayını kaydeder ve listeler (denetim izi) |
| `dashboard.py` | `/dashboard/stats` için referans veri, inceleme faaliyeti ve CN içe aktarmalarının salt-okunur toplulaştırması |
| `risk.py` | classify/screen/duty'yi tek açıklanabilir toplu risk skorunda birleştirir |
| `exceptions.py` | `CustomsIQError` → `InvalidQueryError`, `HSCodeNotFoundError`, `RateNotFoundError` |
| `config.py` | `pydantic-settings`; `CUSTOMSIQ_*` ortam değişkenlerini ve `.env` dosyasını okur |
| `logging_config.py` | Ortak loglama kurulumu — stdout'a sade format, hiçbir yerde `print()` yok |
| `main.py` | Etkileşimli CLI giriş noktası (arama + `screen <isim>`) |
| `api.py` | FastAPI uygulaması: `/` adresinde arayüzü sunar, ayrıca `/search`, `/classify`, `/screen`, `/calculate-duty`, `/review`, `/review/history`, `/codes/{code}/history`, `/dashboard/stats`, `/assess-risk`, `/health` |
| `scripts/import_cn_codes.py` | CLI içe aktarma aracı: CN dosyasını ayrıştırır, değişiklikleri `upsert_hs_codes_with_history()` ile sürümler |
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

CREATE TABLE tariff_rates (
    hs_code           TEXT NOT NULL,  -- örn. "6109100000"
    country_of_origin TEXT NOT NULL,  -- ISO alpha-2 ya da standart MFN için "ALL"
    rate_type         TEXT NOT NULL,  -- "standard" veya "preferential"
    rate_percent      REAL NOT NULL,  -- örn. 12.0
    trade_agreement   TEXT,           -- standart oranlarda NULL
    valid_from        TEXT NOT NULL,  -- oranın yürürlüğe girdiği ISO 8601 tarih
    PRIMARY KEY (hs_code, country_of_origin, valid_from)
);

CREATE TABLE review_decisions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,  -- denetim kaydının doğal anahtarı yok
    subject_type       TEXT NOT NULL,   -- "classification" | "screening" | "duty"
    subject_reference  TEXT NOT NULL,   -- sha256(subject_type + normalize edilmiş girdi)
    decision           TEXT NOT NULL,   -- "approved" | "rejected" | "flagged"
    reviewer_name      TEXT NOT NULL,   -- serbest metin — kimlik doğrulama gelene kadar geçici
    comment            TEXT,            -- opsiyonel not
    reviewed_at        TEXT NOT NULL    -- ISO 8601 zaman damgası
);

CREATE TABLE hs_code_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,  -- geçmiş kaydının doğal anahtarı yok
    code          TEXT NOT NULL,     -- bu sürümün ait olduğu hs_codes.code
    description   TEXT NOT NULL,     -- bu sürümde geçerli olan açıklama
    category      TEXT NOT NULL,     -- bu sürümde geçerli olan kategori
    valid_from    TEXT NOT NULL,     -- bu sürümün geçerli olduğu ISO 8601 zaman damgası
    valid_to      TEXT,              -- değiştirildiği zaman damgası, hâlâ güncelse NULL
    version_label TEXT NOT NULL      -- bu sürümü üreten içe aktarma, örn. "CN2026"
);

CREATE TABLE cn_code_versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    version_label       TEXT NOT NULL,     -- örn. "CN2026"
    source_description  TEXT,              -- örn. içe aktarılan dosyanın adı
    imported_at         TEXT NOT NULL,     -- işlemin tamamlandığı ISO 8601 zaman damgası
    row_count           INTEGER NOT NULL   -- bu çalıştırmada işlenen yaprak CN kodu sayısı
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
| **Varsayılan SQLite, isteğe bağlı Postgres** | Tek düğümlü, ağırlıklı okuma yapılan referans verisi; sıfır operasyon yükü. Bağlantı katmanı artık her ikisini de konuşuyor — `CUSTOMSIQ_DATABASE_URL` hiçbir modüle dokunmadan arka ucu değiştirir | Çoklu yazar eşzamanlılığı veya kalıcı barındırılan durum gerekirse Postgres varsayılan yapılır |
| **`check_same_thread=False` ile tek paylaşımlı bağlantı** | Basit; FastAPI'nin thread havuzuyla çalışır | Eşzamanlı yazmalar ortaya çıktığında bağlantı havuzu |
| **`print()` değil loglama** | CLI ve API için aynı çıktı yolu; seviye yapılandırmayla kontrol edilir | — |
| **Doğrulamanın `matching.py` içinde olması** | Arama, tarama, CLI ve API bunu devralır; yeni bir çağıran eklenerek atlanması imkânsızdır | — |
| **`EmbargoScreeningError` eklenmemesi** | Taramanın girdi doğrulaması aramanınkiyle birebir aynı; yeni sınıf yerine `InvalidQueryError` yeniden kullanılır | Tarama gerçekten farklı bir hata durumu kazanırsa eklenir |
| **`review_decisions`, diğer üç tablonun aksine `INTEGER PRIMARY KEY AUTOINCREMENT` kullanır** | Denetim kayıtlarının doğal bir benzersizliği yok — aynı `subject_reference` zaman içinde birden çok karara sahip olabilir | — |
| **`review_decisions` yalnızca ekleme yapılır (append-only)** | SAP GTS gibi gümrük uyum araçlarında yaygın olan dört-göz / insan-onayı ilkesini modeller: düzeltilmiş bir karar bir güncelleme değil, yeni bir satırdır, böylece geçmiş asla kaybolmaz. `reviewer_name` bu demoda serbest metindir; üretim sistemi bunu kimlik doğrulanmış kullanıcılara bağlar (bkz. Yol haritası) | Kimlik doğrulanmış kullanıcılar + RBAC eklenir |
| **CN kodu geçmişi `hs_codes`'a eklenen `valid_from`/`valid_to` sütunları yerine ayrı bir `hs_code_history` tablosunda tutulur** | `hs_codes` mevcut `code TEXT PRIMARY KEY` yapısını ve iki okuma fonksiyonunu (`fetch_all`, `get_by_code`) birebir aynı korur — süzülecek, unutulacak bir şey yok. Ayrıca göç açısından güvenli tek seçenek: bu projede şema göçü yok ve `CREATE TABLE IF NOT EXISTS` mevcut bir tabloyu asla değiştirmez, dolayısıyla `hs_codes`'a eklenen sütunlar mevcut hiçbir `customsiq.db` dosyasında görünmezdi | Gerçek bir dağıtım ilk günden tam derinlikli geçmiş istiyorsa mevcut her kod için açılış geçmiş satırı geri doldurulur |

### 🕘 Sürümlü CN kodları (SCD Type 2)

CN referans verisini yeniden içe aktarmak, `hs_codes`'u yerinde sessizce eziyordu
(`ON CONFLICT DO UPDATE`) — bir sınıflandırma veya vergi kararı eski bir açıklamaya karşı
verildiyse ve nomanklatür daha sonra değişmiş veriyle yeniden içe aktarıldıysa, sistemin karar
anında "ne bildiğini" yeniden kurmanın bir yolu yoktu. `scripts/import_cn_codes.py` artık BI/veri
ambarı araçlarında yaygın olan SCD Type 2 desenini kullanarak her gerçek değişikliği sürümlüyor
(SAP BW'nin değişiklik-belgesi tabloları aynı fikirdir): `hs_codes` öncekiyle birebir aynı şekilde
kod başına tek güncel satır tutmaya devam eder, `hs_code_history` ise her önceki değeri —
silinmeden, kapatılarak — saklar.

"CN2025" (yeni bir kod), ardından "CN2026" (aynı kod, açıklama yeniden yazılmış) içe aktarıldığında:

| Tablo | CN2025 sonrası | CN2026 sonrası |
|---|---|---|
| `hs_codes` | `6109100000` → *"Cotton T-shirts, knitted"* | `6109100000` → *"Cotton T-shirts, knitted or crocheted"* (eski değer burada yok — tıpkı bugünkü gibi) |
| `hs_code_history` | tek açık satır: *"...knitted"*, `valid_to = NULL`, `version_label = "CN2025"` | o satır artık **kapalı** (`valid_to` set edilmiş) **artı yeni bir açık satır**: *"...knitted or crocheted"*, `version_label = "CN2026"` |
| `cn_code_versions` | `CN2025`, `row_count = 1` | `CN2026`, `row_count = 1` |

`GET /codes/6109100000/history` her iki `hs_code_history` satırını da, en eskisi önce olacak
şekilde döndürür — eski açıklama silinmez, hayatta kalır. "CN2026"yı **aynı** veriyle ikinci kez
içe aktarmak hiçbir geçmiş tablosuna bir şey eklemez: yalnızca `cn_code_versions`, çalıştırmanın
0 değişiklikle gerçekleştiğini kaydeder. `search.py`, `cn_classifier.py`, `tariff_calculator.py`
ve `embargo_screener.py` bunların hiçbirinden etkilenmez — `tariff_calculator.py` `hs_codes`'u
hiç okumaz, diğer ikisi zaten yalnızca `fetch_all()` çağırır ve bu her zaman döndürdüğünü döndürür.

Bu aynı zamanda insan-onayı katmanındaki denetim izini de güçlendirir: `review_decisions` bir
kararın incelendiğini kaydeder, CN kodu geçmişi ise artık o anda hangi nomanklatür verisinin
etkin olduğunu yeniden kurmayı mümkün kılar.

### 📊 Gösterge paneli: Faz 1 ve 2 üzerine raporlama katmanı

`dashboard.py` hiçbir yeni iş mantığı eklemez ve hiçbir karar vermez — `review.py`'nin ve CN
hattının zaten kaydettiği verilerin salt-okunur bir toplulaştırmasıdır; mevcut `database.py`
okumalarını (`fetch_all`, `fetch_all_entities`, `fetch_review_decisions`, `fetch_cn_import_runs`,
artı iki küçük yeni sayma yardımcısı) frontend'in Gösterge Paneli için tek bir `GET
/dashboard/stats` çağrısında birleştirir. Belirtilmeye değer bir uyarlama: `cn_code_versions`
(Faz 2) her zaman yalnızca `row_count` saklamıştır, yeni/değişen/değişmeyen ayrımını değil — o
ayrım yalnızca `upsert_hs_codes_with_history()` içinde geçici olarak var oldu ve hiçbir yere
kaydedilmedi. Bunu geriye dönük saklamak için sütun eklemek yerine, gösterge paneli her
çalıştırma için **değişen ve değişmeyen** sayısını, `hs_code_history`'de o çalıştırmanın
`version_label`'ını taşıyan kaç satır olduğundan türetir (üç ayrı sayım değil, tek bir `GROUP BY`
sorgusu) — bu, gerçekte kaydedilenin dürüst bir okunuşudur, uydurulmuş bir dağılım değil.

### ⚠️ Toplu risk skorlama

Gerçek risk tabanlı gümrük kontrolleri (SAP GTS "Legal Control" dahil) sınıflandırma, tarama ve
vergiyi bağımsız olarak puanlamaz — bir sevkiyatın genel riski üçünün birlikte bir fonksiyonudur.
`risk.py`, `classify()`, `screen_entity()` ve `calculate_duty()`'yi — mevcut genel imzalarıyla,
hiçbir yenilik olmadan — çağıran `assess_shipment()`'ı ekler ve üçünü tek bir toplu skorda
birleştirir:

```
toplu = 0.6 × tarama + 0.25 × sınıflandırma + 0.15 × vergi      (her faktör [0, 1] arasında)
seviye = toplu ≥ 0.5 ise "yüksek", ≥ 0.2 ise "orta", aksi hâlde "düşük"
```

| Faktör | Ağırlık | Kural | Neden |
|---|---|---|---|
| **Tarama** | 0,6 | Gerçek eşleşme → `1,0`; yakın-ıskala (uyum eşiği 0,75'e karşı yalnızca daha düşük bir izleme eşiği 0,55'te bir eşleşme) → `0,4`; hiçbiri → `0,0` | Gerçek bir eşleşme diskalifiye edicidir, sadece riskli değil — 0,6 ağırlıkta, tek başına bir eşleşme (`0,6`) diğer iki faktör ne kadar temiz olursa olsun "yüksek"i zaten geçer |
| **Sınıflandırma** | 0,25 | `1 − en_iyi_güven`; hiç eşleşme yok → `1,0`; kod doğrudan verilmiş (çıkarılacak bir şey yok) → `0,0` | Düşük güven, yanlış HS kodunun uygulanabileceği anlamına gelir — bir uyum ihlali değil, veri kalitesi sorunudur, dolayısıyla taramanın ağırlığının çok altındadır |
| **Vergi** | 0,15 | `min(oran_yüzdesi / 20, 1,0)`, tercihliyse `+0,15`, `1,0`'a kırpılır; oran yoksa sabit `0,6` | %20, tohumlanan en yüksek standart orandan (%16,9, ayakkabı) yüksektir; tercihli bonus gerçek bir dolandırıcılık vektörünü yansıtır — bir ticaret anlaşması iddiası, sonuç oranı düşük veya sıfır olsa bile denetimde yeniden doğrulanacak tam olarak budur |

Açıkça belirtilmesi gereken iki şey, ima edilmeden:

- **Vergi faktörü kırpılır**, `min(min(oran_yüzdesi/20, 1) + 0,15, 1,0)` — sadece kırpılmamış
  `+ 0,15` değil. Veri modelinde `TariffRate.rate_percent`'i sınırlayan hiçbir şey yok, dolayısıyla
  %20 tavanında veya üzerinde tercihli bir oran, bugünün örnek verisi böyle bir şey içermese bile
  şemanın izin verdiği gerçek bir olasılıktır — kırpma, bugünün fikstürlerine değil veri modelinin
  şartlarına göre doğrudur ve sentetik bir %90 oran kullanan özel bir testle kapsanır.
- **Denetim kaydı yok.** Bir risk değerlendirmesi kalıcı hale getirilmez ve `review_decisions`
  üzerinden incelenebilir değildir — yeniden hesaplamak ucuzdur (üç mevcut fonksiyon çağrısı,
  yeni G/Ç yok) ve incelenebilir yapmak, bu fazın bilinçli olarak dokunmadığı `review.py`'nin
  kapalı `_VALID_SUBJECT_TYPES` kümesini genişletmek anlamına gelirdi. Zaten bir risk
  değerlendirmesi yeni bir karar türü değil — zaten incelenebilir olan üç karar üzerine bir
  mercek; bir incelemeciye onaylanacak/reddedilecek dördüncü bir şey eklemek yerine, o üçünden
  *hangisine* önce bakması gerektiğini söyler.

Üç alttaki çağrının herhangi birinden gelen `InvalidQueryError` (hatalı HS kodu, yanlış ülke,
negatif değer) asla yakalanıp bir skora çevrilmez — kötü girdi bir istek sorunudur ve diğer her
uç nokta gibi HTTP `400` olarak yüzeye çıkar. CLI'nin `risk` komutu yalnızca HS kodu yolunu
destekler, serbest metin açıklamayı değil: düz bir REPL satırı iki ayrı serbest metin alanını
(açıklama ve taraf ismi) belirsizlik olmadan tutamaz — `duty <kod> <ülke> <değer>` ve
`screen <isim>`'in her birinin tek bir alan tutabildiği gibi. API ve frontend (yapılandırılmış
form alanları) ikisini de destekler.

### 🐳 Docker: yerel geliştirme için, Render için değil (henüz)

Render servisi hiç Dockerfile ile yapılandırılmamış bir repoya Dockerfile eklemek, yapmadan önce
düşünülmesi gereken tam olarak bu tür bir değişikliktir — bir servisin Language'ı Docker'a
ayarlıysa Render bir `Dockerfile`'dan build *edebilir*, ve bunu yanlış anlamak canlı demonun
bugünkünden farklı build/start olmasına yol açabilir. Hiçbir şey yazmadan önce Render'ın kendi
belgelerine karşı araştırıldı: Docker'ı etkinleştirmek **servis oluşturma anı**na ait bir
dashboard ayarı olarak tarif edilir (*"Render Dashboard'da şu ayarları servis oluşturma
sırasında uygulayın: 1. Language alanını Docker'a ayarlayın"*) — daha sonraki bir push'ta bir
`Dockerfile` belirdiği için *zaten oluşturulmuş* bir servisin runtime'ı yeniden algılayıp
değiştirmesine dair belgelenmiş bir mekanizma yok. Bu repoda ayrıca `render.yaml` veya Procfile
yok, bu da canlı servisin build/start komutlarının ve runtime'ının tamamen Render'ın
dashboard'unda, bu reponun dışında yaşadığını doğruluyor — buraya dosya push etmek onu yeniden
yazamaz.

Bunu göz önünde bulundurarak, `Dockerfile`/`docker-compose.yml` — araştırmanın zaten mevcut bir
servise uygulanmadığını söylediği bir algılama mekanizmasından kaçınmak için bir alt dizine
gizlenmek yerine — repo kökünde (geleneksel konum) yaşıyor. Bir insanın tek seferlik kontrol
etmesi gereken tek şey: bu servis için Render dashboard'unu açıp Language/Runtime'ın hâlâ
mevcut yerel ayarında olduğunu, "Docker" olmadığını doğrulamak — yukarıdaki gerekçe göz önüne
alındığında maliyetsiz bir doğrulama, beklenen bir sorun değil, çünkü o dashboard'u kendim
görüp doğrudan doğrulayamıyorum.

### 🐘 Çift arka uç: varsayılan SQLite, isteğe bağlı Postgres

Postgres, SQLite'ın *yerine* değil *yanına* eklendi ve gerekçe bir zevk meselesi değil, bir maliyet
argümanı.

**Neden tamamen geçilmedi.** Tüm test paketi `:memory:` üzerinde, sunucusuz ve sürücüsüz, bir
saniyenin çok altında çalışıyor; tam geçiş, davranışı her iki tarafta da aynı olan kodu test etmek
için her yerel `pytest`'i canlı bir PostgreSQL'e (ya da testcontainers'a) bağımlı kılardı. Canlı demo
da bir şey kazanmaz — bilinçli olarak kurgusal veriyle, hızlı soğuk başlatmayla ve sıfırlanan bir
dosya sistemiyle çalışır; yeniden tohumlama tasarımın parçasıdır, Postgres'in düzelteceği bir kusur
değil. Barındırma maliyeti de gerçek: **Render'ın ücretsiz PostgreSQL'i oluşturulmasından 30 gün
sonra sona erer** (ücretli plana yükseltilmedikçe erişilemez; kalıcı silmeden önce 14 günlük ek
süre, çalışma alanı başına bir ücretsiz veritabanı, 1 GB) — [Render belgeleri](https://render.com/docs/free).
Her ay sessizce bozulan bir portföy bağlantısı, ayakta kalan birinden kötüdür. Tek bir SQL setini
iki arka uçta çalıştırmak, birini seçmekten fazlasını da gösterir: veri katmanının gerçekten soyut
olduğunu.

**Neden ~150 satırlık bir adaptör, SQLAlchemy Core değil.** `openpyxl` ve scikit-learn kararlarıyla
aynı test: bağımlılık, çözmesi beklenen sorunu ortadan kaldırıyor mu? Kaldırmıyor. Buradaki en zor
lehçe farkı — `ON CONFLICT … DO UPDATE` — iki arka uçta *birebir aynı*; Core'un upsert'ü ise
lehçeye özgü (`dialects.postgresql.insert` ile `dialects.sqlite.insert`), yani dallanma yine kalırdı.
Buna karşılık Core, SQLite yolundaki ~18 ifadenin tamamını — yani canlı sitenin çalıştırdığı yolu —
yeniden yazar ve her varsayılan test çalışmasına yeni bir import sokardı. `src/customsiq/pg_adapter.py`
yalnızca `get_connection`'ın Postgres dalında, tembel biçimde içe aktarılır; böylece `psycopg` isteğe
bağlı bir ek olarak kalır. Sınırı kaynakta işaretli: `?` → `%s` çevirisi naif bir değiştirmedir,
hiçbir ifade düz `?` veya `%` içermediği sürece yeterlidir (hepsini tarayan bir test var); ötesinde
daha fazla regex değil, sqlglot veya Core.

**Gerçekte ne farklı — varsayılmadı, gerçek bir `postgres:16` konteynerine karşı doğrulandı:**

| | SQLite | PostgreSQL | Ele alınışı |
|---|---|---|---|
| Yer tutucular | `?` | `%s` | adaptörde çevrilir |
| `id` sütunları | `INTEGER PRIMARY KEY AUTOINCREMENT` | karşılığı yok | `GENERATED ALWAYS AS IDENTITY` olarak yeniden yazılır |
| `rate_percent REAL` | 8 baytlık float | **4 baytlık `float4`** — `16.9` geri okunurken `16.899999618…` olur | `DOUBLE PRECISION`'a çevrilir; bir test tam olarak `== 16.9` olduğunu doğrular |
| Yeni satır kimliği | `cursor.lastrowid` | psycopg'de yok | yalnızca Postgres'te `… RETURNING id`; SQLite yolu mevcut sırasını birebir korur |
| `FROM (SELECT …)` | takma ad isteğe bağlı | PG 16 öncesi zorunlu | `AS changed_codes` eklendi (ikisinde de geçerli) |
| Çok ifadeli `SCHEMA` | `executescript` | böyle bir metot yok | adaptör bölüp her ifadeyi çalıştırır |
| Metin `ORDER BY` | bayt sırası | derlemeye (collation) bağlı | compose veritabanı `--locale=C` ile oluşturulur |
| Satır biçimi | tuple | tuple *(psycopg'nin varsayılanı)* | açıkça `tuple_row`'a sabitlendi — buradaki her satır konumsal okunur (`HSCode(*row)`), `dict_row` ise sütun **adlarını** alanlara yerleştirip sessizce çöp üretirdi |

Sıralanmamış `SELECT`'lerin satır sırası iki arka uçta da garanti değildir; bu nedenle arama
sıralamasındaki eşitlikler farklı sırayla gelebilir. Bunu "düzeltmek" için `ORDER BY` eklenmedi —
bugünkü SQLite davranışını değiştirirdi — ve parite testleri bilinçli olarak eşitlik sırası
doğrulamaz.

**Postgres şeması tek bir SQLite `SCHEMA` metninden türetilir**, ikinci bir kopya olarak tutulmaz;
böylece iki arka uç birbirinden ayrışamaz. Yedi karar modülü, `sqlite3.Connection` tip
açıklamalarına kadar değişmedi: hiçbiri SQL çalıştırmaz, yalnızca `conn`'u `database.py`'ye geri
verir; bu yüzden Postgres dalı sarmalayıcıyı `cast` ile döndürür.

### 🔗 Deterministik `subject_reference`

İncelenebilir her sonuç bir `subject_reference` taşır — `sha256(f"{subject_type}:{normalize_edilmis_girdi}")`
— böylece aynı sorgu tekrar gönderildiğinde her zaman aynı konuyu denetler; tekrar gönderimler yeni
bir geçmiş açmak yerine paylaşılan tek bir inceleme geçmişine bağlanır. `subject_type` ön eki, üç
yeteneğin aynı hash üzerinde çakışmasını engeller.

Normalizasyon, metin girdilerinde bilinçli olarak büyük/küçük harf duyarsızdır (karar
büyük/küçük harfle değişmez) ama parasal değerde tam eşleşme ister (farklı bir gümrük kıymeti
**farklı** bir karardır):

| Konu türü | Girdi | `subject_reference` | Aynı girdi tekrar? |
|---|---|---|---|
| classification | `"knitted cotton shirt"` | `ca8b1b95…fc3407` | Aynı |
| classification | `"KNITTED COTTON SHIRT"` | `ca8b1b95…fc3407` | **Yukarıdakiyle aynı** — hash'lemeden önce büyük/küçük harf birleştirilir |
| screening | `"Northwind Maritime"` | `fa9ec5ed…b32c38c` | Aynı |
| duty | `hs_code=6109100000, country=DE, value=1000.00` | `8e4b03f6…602e3c2e` | Aynı |
| duty | `hs_code=6109100000, country=DE, value=1000.01` | `0a16c715…9c8f53` | **Farklı** — farklı bir kıymet, denetlenecek farklı bir karardır |

(Tam hash değerleri ve aynı doğrulamalar `tests/test_review.py::TestDeterminism` içinde bulunur.)

### 🧠 `/search` ile `/classify` — tek veri, iki algoritma

İkisi de aynı `hs_codes` tablosunu sıralar, ama farklı sorulara yanıt verir ve farklı şekillerde
hata yapar. `/search` bir **arama**dır: hızlı karakter örtüşmesi, ifadeyi aşağı yukarı bildiğinizde
iyidir. `/classify` bir **öneri motorudur**: her kelimenin nomanklatür genelinde ne kadar *nadir*
olduğunu tartar; böylece ayırt edici bir terim, yaygın olandan daha fazla ağırlık taşır ve hangi
terimlerinizin sonucu getirdiğini bildirir.

Örnek veri kümesi üzerinde ölçülen:

| Sorgu | `/search` (difflib) | `/classify` (TF-IDF) | |
|---|---|---|---|
| `knitted cotton shirt` | `6203420000` Erkek pamuklu **pantolon** | `6109100000` **Pamuklu tişört, örme** | ✅ classify doğru |
| `lithium battery` | `8507600000` Lityum iyon piller | aynı | berabere |
| `laptop` | `3926909700` Plastik ev eşyaları | `8471300000` dizüstü | ✅ classify doğru |

1. satır bu modülün varlık sebebidir: `knitted` yalnızca tek bir açıklamada geçer, bu yüzden terim
ağırlıklandırması onun baskın olmasını sağlar; karakter örtüşmesi ise "cotton trousers" ile
paylaşılan harf yığınına kanar. 3. satır ters yöndeki hatayı gösterir: difflib ne olursa olsun
*bir şey* döndürür, classify ise hiçbir terim paylaşılmadığında gürültüyü öneri kılığına sokmak
yerine hiçbir şey döndürmez.

**Neden elle yazılmış TF-IDF, scikit-learn değil.** Uygulama, sklearn'ün kendi formülüdür
(yumuşatılmış IDF `log((N+1)/(df+1))+1`, L2 normalize vektörler, iç çarpımla kosinüs) ve ~40 satır
standart kütüphane aritmetiğidir; yani `TfidfVectorizer` bu veriyi neredeyse aynı sıralardı —
kapatılacak bir doğruluk açığı yok. Buna karşılık scikit-learn, 20 satırlık bir tabloyu sıralamak
için üretim imajına numpy ve scipy'ı (~100 MB) sokar. Ve belirleyici olan: **açıklanabilirlik
sklearn ile daha az değil, daha çok kod isterdi** — burada her terimin katkısı zaten skora giderken
hesaplanan `sorgu_ağırlığı × belge_ağırlığı`; sklearn ile aynı sayıları geri elde etmek için
`vectorizer.vocabulary_` içine uzanıp seyrek matrise indekslemek gerekirdi.

Veri kümesi ~10⁵ satırı aşarsa ya da n-gram veya alt-doğrusal terim frekansı gerekirse
scikit-learn'e geçilir. Ondan önce sınıflandırıcı indeksi her çağrıda yeniden kurulur — 20 kodda
0,1 ms, 10 000 kodda ~68 ms — yani ilk optimizasyon yeni bir bağımlılık değil, önbelleklemedir.

**Ölçümden çıkan bir ayrıntı:** CN açıklamaları çoğul yazılır ("cables", "batteries"), kullanıcılar
ise tekil yazar. Çoğul katlaması olmadan `cable`, `biscuit`, `laptop` ve `battery` sorgularının her
biri **her koda karşı sıfır** skor aldı. Bu yüzden tokenizer `-ies → y`, ıslıklı `-es` ve `-s`
eklerini katlar. Bu bir gövdeleyici (stemmer) değil — yalnızca korpusun gerektirdiği İngilizce
çoğul kuralı.

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
| `CUSTOMSIQ_DATABASE_URL` | *(tanımsız)* | `postgresql://…` URL'i. **Tanımlıyken `CUSTOMSIQ_DATABASE_PATH`'e göre önceliklidir**; tanımsız veya boşsa eskisi gibi SQLite kullanılır. Başka bir şema açılışta reddedilir |
| `CUSTOMSIQ_LOG_LEVEL` | `INFO` | Python log seviyesi (`DEBUG`, `INFO`, `WARNING`, …) |
| `CUSTOMSIQ_SCREENING_THRESHOLD` | `0.75` | Tarama eşleşmesi için asgari isim benzerlik skoru (0–1) |

### 🐳 Docker ile çalıştırma

Yalnızca yerel geliştirme için — **[canlı demo](https://customsiq-gs0u.onrender.com/) Render'ın
mevcut yerel (native) Python dağıtımını kullanmaya devam ediyor, bundan etkilenmiyor.**
`render.yaml` yok, Procfile yok; bu repo Render'a hiçbir zaman nasıl dağıtım yapacağını
söylemedi, dolayısıyla buraya bir `Dockerfile` eklemek onu etkilemiyor. Gerekçe için aşağıdaki
[🐳 Docker: yerel geliştirme için, Render için değil (henüz)](#-docker-yerel-geli%C5%9Ftirme-i%C3%A7in-render-i%C3%A7in-de%C4%9Fil-hen%C3%BCz)
bölümüne bakın. Yine de değerli: bu projeyi elle Python venv kurmadan inceleyen veya çalıştıran
herkes için ortam paritesi, ve isteğe bağlı PostgreSQL servisinin üzerine kurulduğu temel —
aşağıdaki [🐘 PostgreSQL ile çalıştırma](#-postgresql-ile-çalıştırma) bölümüne bakın.

```bash
docker build -t customsiq .
docker run -p 8000:8000 customsiq
```

Ya da yerel geliştirme için, `docker-compose.yml` `.env.example` ile aynı üç ayarı bağlar ve
yeniden başlatmalar arasında tohumlanan veritabanının hayatta kalması için adlandırılmış bir
volume ekler:

```bash
docker compose up
```

İkisi de `uvicorn`'u doğrudan çalıştırmakla aynı şekilde **http://localhost:8000/**'de servis
verir. Çok aşamalı build, `python:3.11-slim` (bu makinenin rastgele yerel sürümü değil, CI'nin
`actions/setup-python` sürümüyle eşleşecek şekilde sabitlenmiş) — üretim imajı yalnızca beş
çalışma zamanı paketini kurar (`requirements-runtime.txt`), geliştirme araçlarını
(ruff/black/mypy/pytest) veya yalnızca test amaçlı bağımlılıkları (`httpx`, yalnızca
`fastapi.testclient.TestClient` için gerekli) asla kurmaz. Sıcak yeniden yükleme
bağlanmamıştır — kod değişikliğinden sonra yeniden build edin; burada "yerel geliştirme"nin
gerektirdiği bilinçli bir sadeleştirme, bir eksiklik değil.

### 🐘 PostgreSQL ile çalıştırma

**İsteğe bağlı, yalnızca yerel. [Canlı demo](https://customsiq-gs0u.onrender.com/) SQLite'ta
kalıyor** — bunun yarım kalmış bir göç değil, bilinçli bir tercih olmasının nedeni için
[🐘 Çift arka uç: varsayılan SQLite, isteğe bağlı Postgres](#-çift-arka-uç-varsayılan-sqlite-isteğe-bağlı-postgres)
bölümüne bakın.

`docker-compose.yml` bir `postgres:16-alpine` servisini bir **profil** arkasında taşır; böylece düz
bir `docker compose up` her zamanki SQLite kurulumunun aynısıdır. Hem profil hem de URL ile açın:

```bash
CUSTOMSIQ_DATABASE_URL=postgresql://customsiq:customsiq@postgres:5432/customsiq \
  docker compose --profile postgres up
```

Docker dışında önce isteğe bağlı sürücüyü kurun (`requirements.txt` içinde **yoktur**):

```bash
pip install -r requirements-postgres.txt
CUSTOMSIQ_DATABASE_URL=postgresql://customsiq:customsiq@localhost:5432/customsiq \
  uvicorn src.customsiq.api:app
```

Şema, SQLite dosyasında olduğu gibi ilk bağlantıda oluşturulur. PostgreSQL parite testlerini
çalıştırmak için adında `test` geçen bir veritabanı gösterin — fixture tüm tabloları düşürür ve
aksi hâlde çalışmayı reddeder:

```bash
docker compose --profile postgres up -d postgres
docker exec customsiq-postgres-1 psql -U customsiq -d customsiq -c "CREATE DATABASE customsiq_test;"
CUSTOMSIQ_TEST_POSTGRES_URL=postgresql://customsiq:customsiq@localhost:5432/customsiq_test \
  pytest tests/test_postgres.py
```

Bu değişken olmadan atlanırlar; böylece varsayılan `pytest` çalışması hızlı ve bağımlılıksız kalır.

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
'classify <description>' for ranked suggestions with reasoning,
'screen <name>' to run a sanctions check,
or 'duty <hs_code> <country> <value>' to calculate customs duty.

> cotton t-shirt
1. 6109100000  (74%)  Cotton T-shirts, knitted        [Textile]
2. 6203420000  (57%)  Men's cotton trousers           [Textile]
3. 6204620000  (54%)  Women's cotton trousers         [Textile]
4. 6110200000  (42%)  Cotton pullovers and sweaters   [Textile]
5. 8528721000  (35%)  Color television receivers      [Electronics]

> screen Northwind Maritime
1 potential sanctions match(es) for 'Northwind Maritime':
1. Northwind Maritime Holdings Ltd  (100%)  [CY]  EU Consolidated Financial Sanctions List  listed 2023-04-12

> classify knitted cotton shirt
1. 6109100000  (85% confidence)  Cotton T-shirts, knitted  [Textile]  via: shirt, knitted, cotton
2. 6203420000  (19% confidence)  Men's cotton trousers  [Textile]  via: cotton

> screen Quokka Beachwear
No sanctions match for 'Quokka Beachwear'.

> duty 6109100000 NO 1000
Duty on 6109100000 from NO: 0.00 (0.00% preferential)
  Preferential rate of 0% applied under the EU-Solvia Free Trade Agreement, for which origin NO qualifies.
  Customs value 1000.00 + duty 0.00 = 1000.00

> review duty 8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e approved alice confirmed correct
Recorded: approved 1 on duty:8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e by alice at 2026-01-01T12:00:00+00:00

> review-history
2026-01-01T12:00:00+00:00  duty:8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e  approved  by alice  (confirmed correct)

> risk 6109100000 NO 1000 Northwind Maritime
Risk for 6109100000 from NO, party 'Northwind Maritime': HIGH (0.6609)
  screening       1.0000 (weight 0.60)  real sanctions match: Northwind Maritime Holdings Ltd (1.00)
  classification  0.0000 (weight 0.25)  HS code given directly
  duty            0.1500 (weight 0.15)  preferential rate 0.0%
```

CLI'nin `risk` komutu yalnızca HS kodu yolunu destekler (`risk <hs_kodu> <ülke> <değer>
<taraf_ismi>`), serbest metin açıklamayı değil — nedeni için
[⚠️ Toplu risk skorlama](#️-toplu-risk-skorlama) bölümüne bakın. API ve web arayüzü açıklamayı
da destekler.

### 🖥️ Web arayüzü

```bash
uvicorn src.customsiq.api:app --reload
```

**[Canlı demoyu](https://customsiq-gs0u.onrender.com/)** deneyin, ya da yerelde çalıştırırken web
arayüzü için **http://localhost:8000/** adresini açın — her iki yetenek tek sayfada.

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
| `GET` | `/classify` | Güven skoru ve eşleşen terimlerle sıralanmış kod önerileri |
| `GET` | `/screen` | Kişi veya kuruluş ismi için yaptırım listesi eşleşmeleri |
| `GET` | `/calculate-duty` | Sevkiyat için ödenecek vergi, uygulanan oranın gerekçesiyle |
| `POST` | `/review` | Geçmiş bir sınıflandırma, tarama veya vergi sonucu için inceleyici kararını kaydeder |
| `GET` | `/review/history` | Kayıtlı inceleme kararları, en yeni önce |
| `GET` | `/codes/{code}/history` | Bir CN kodunun SCD Type 2 sürüm zaman çizelgesi, en eski önce |
| `GET` | `/dashboard/stats` | Toplu istatistikler: referans veriler, inceleme faaliyeti, CN içe aktarma çalıştırmaları |
| `GET` | `/assess-risk` | Sınıflandırma, tarama ve vergiyi birleştiren toplu risk skoru |
| `GET` | `/docs` | Etkileşimli Swagger arayüzü (otomatik üretilir) |

**`GET /search` parametreleri**

| Parametre | Tip | Varsayılan | Kısıtlar | Açıklama |
|---|---|---|---|---|
| `q` | `str` | *zorunlu* | 1–500 karakter, boş olamaz | Serbest metin ürün açıklaması |
| `limit` | `int` | `5` | 1–50 | Azami sonuç sayısı |

**`GET /classify` parametreleri**

| Parametre | Tip | Varsayılan | Kısıtlar | Açıklama |
|---|---|---|---|---|
| `description` | `str` | *zorunlu* | 1–500 karakter, boş olamaz | Eşyanın serbest metin açıklaması |
| `top_n` | `int` | `5` | 1–50 | Azami öneri sayısı |

İkinci sıradaki önerinin skoru çok daha düşüktür; çünkü yalnızca *yaygın* olan `cotton` kelimesini
paylaşır, kazanan ise nadir olan `knitted` ile de eşleşir — `matched_terms` bunu ima etmek yerine
görünür kılar.

**`GET /screen` parametreleri**

| Parametre | Tip | Varsayılan | Kısıtlar | Açıklama |
|---|---|---|---|---|
| `name` | `str` | *zorunlu* | 1–500 karakter, boş olamaz | Taranacak kişi veya kuruluş ismi |

Tarama `limit` almaz: eşiğin üzerindeki her eşleşme döndürülür; sessizce kırpılmış bir eşleşme
listesi, kötü bir sıralamadan öte bir uyum ihlali olurdu.

**`GET /calculate-duty` parametreleri**

| Parametre | Tip | Varsayılan | Kısıtlar | Açıklama |
|---|---|---|---|---|
| `hs_code` | `str` | *zorunlu* | CN-8 veya TARIC-10 | İthal edilen eşyanın kodu |
| `country_of_origin` | `str` | *zorunlu* | ISO 3166-1 alpha-2 | Eşyanın menşei |
| `customs_value` | `float` | *zorunlu* | >= 0 | Beyan edilen gümrük kıymeti |

Menşe bir tercihli orana hak kazanıyorsa o oran uygulanır; aksi hâlde standart MFN oranı geçerlidir.
Kayıtta **hiç** oranı olmayan bir kod sıfır vergi değil `404` döndürür — tarife verisindeki bir
boşluk, vergisiz ithalat anlamına gelmez.

**`POST /review` gövdesi**

| Alan | Tip | Varsayılan | Kısıtlar | Açıklama |
|---|---|---|---|---|
| `subject_type` | `str` | *zorunlu* | `classification` \| `screening` \| `duty` | İncelenen sonucun türü |
| `subject_reference` | `str` | *zorunlu* | boş olamaz | O sonucun `subject_reference` değeri — asla yeniden yazılmaz, API'nin döndürdüğü değer kullanılır |
| `decision` | `str` | *zorunlu* | `approved` \| `rejected` \| `flagged` | İnceleyicinin kararı |
| `reviewer_name` | `str` | *zorunlu* | boş olamaz | Serbest metin — kimlik doğrulama gelene kadar geçici |
| `comment` | `str \| null` | `null` | — | Opsiyonel not |

```bash
curl -X POST "http://localhost:8000/review" \
  -H "Content-Type: application/json" \
  -d '{"subject_type": "duty", "subject_reference": "8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e", "decision": "approved", "reviewer_name": "alice", "comment": "confirmed correct"}'
```

```json
{
  "id": 1,
  "subject_type": "duty",
  "subject_reference": "8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e",
  "decision": "approved",
  "reviewer_name": "alice",
  "comment": "confirmed correct",
  "reviewed_at": "2026-01-01T12:00:00+00:00"
}
```

**`GET /review/history` parametreleri**

| Parametre | Tip | Varsayılan | Kısıtlar | Açıklama |
|---|---|---|---|---|
| `subject_type` | `str \| null` | `null` | `classification` \| `screening` \| `duty` | Bu türle sınırla |
| `subject_reference` | `str \| null` | `null` | — | Bu konuyla sınırla |
| `limit` | `int` | `50` | 1–200 | Azami kayıt sayısı |

```bash
curl "http://localhost:8000/review/history?subject_type=duty&limit=10"
```

**`GET /codes/{code}/history`** — kodun kendisi dışında parametre almaz. Kod bilinmiyorsa `404`;
kod var ama hiçbir sürümlü içe aktarmaya konu olmadıysa (örn. tohumlanan demo verisi) `200 []`
döner, hata değil — `/search` ile aynı "boş liste, asla hata değil" kuralı.

```bash
curl "http://localhost:8000/codes/6109100000/history"
```

```json
[
  {
    "code": "6109100000",
    "description": "Cotton T-shirts, knitted",
    "category": "Textile",
    "valid_from": "2025-01-15T09:00:00+00:00",
    "valid_to": "2026-02-01T09:00:00+00:00",
    "version_label": "CN2025"
  },
  {
    "code": "6109100000",
    "description": "Cotton T-shirts, knitted or crocheted",
    "category": "Textile",
    "valid_from": "2026-02-01T09:00:00+00:00",
    "valid_to": null,
    "version_label": "CN2026"
  }
]
```

**`GET /dashboard/stats`** — parametre almaz, doğrulanacak bir girdi yok. `review_by_decision` ve
`review_by_subject_type` her zaman üç anahtarı da `0` varsayılanıyla taşır, böylece taze bir
veritabanı çağıranı eksik anahtarlara karşı korumaya zorlamadan temiz görüntülenir.

```bash
curl "http://localhost:8000/dashboard/stats"
```

```json
{
  "hs_code_count": 20,
  "sanctioned_entity_count": 18,
  "tariff_rate_count": 18,
  "review_total": 2,
  "review_by_decision": { "approved": 1, "rejected": 0, "flagged": 1 },
  "review_by_subject_type": { "classification": 1, "screening": 0, "duty": 1 },
  "recent_reviews": [ { "id": 2, "subject_type": "duty", "decision": "flagged", "...": "..." } ],
  "import_run_count": 1,
  "recent_import_runs": [
    {
      "version_label": "CN2026",
      "source_description": "cn2026.csv",
      "imported_at": "2026-02-01T09:00:00+00:00",
      "row_count": 10,
      "changed_count": 1,
      "unchanged_count": 9
    }
  ],
  "versioned_code_count": 1
}
```

**`GET /assess-risk`** — `description`/`hs_code`'dan tam olarak biri zorunludur (ikisi de
verilmezse veya ikisi de verilirse `400`); `country_of_origin`, `party_name` ve `customs_value`
her zaman zorunludur. `classify()`, `screen_entity()` ve `calculate_duty()`'yi birleştirir —
ağırlıklar ve gerekçe için [⚠️ Toplu risk skorlama](#️-toplu-risk-skorlama) bölümüne bakın. Bu
örnek, aksi hâlde temiz sınıflandırma/vergi verisine karşı gerçek bir yaptırım eşleşmesidir —
tarama tek başına (ağırlık 0,6) "yüksek"e ulaşmaya yeter:

```bash
curl "http://localhost:8000/assess-risk?description=cotton+t-shirt&country_of_origin=NO&party_name=Northwind+Maritime&customs_value=1000"
```

```json
{
  "level": "high",
  "composite_score": 0.6608770728095686,
  "hs_code": "6109100000",
  "factors": [
    {
      "name": "screening",
      "score": 1.0,
      "weight": 0.6,
      "explanation": "real sanctions match: Northwind Maritime Holdings Ltd (1.00)"
    },
    {
      "name": "classification",
      "score": 0.1535082912382748,
      "weight": 0.25,
      "explanation": "top match 6109100000 at 84.65% confidence"
    },
    {
      "name": "duty",
      "score": 0.15,
      "weight": 0.15,
      "explanation": "preferential rate 0.0%"
    }
  ]
}
```

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
    "score": 1.0,
    "subject_reference": "fa9ec5ed3f84ae68c8c5729faa18e043297e7ec78aae9ab89bebeef82b32c38c"
  }
]
```

**Durum kodları**

| Kod | Anlamı |
|---|---|
| `200` | Başarılı — eşleşme dizisi (boş olabilir) |
| `400` | `InvalidQueryError` — boş/çok uzun sorgu, hatalı kod veya negatif kıymet |
| `404` | `RateNotFoundError` — o HS kodu için kayıtlı vergi oranı yok, veya `/codes/{code}/history`'de `HSCodeNotFoundError` |
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
| `cn_classifier.py` · `exceptions.py` · `models.py` · `search.py` · `tariff_calculator.py` · `review.py` · `dashboard.py` · `risk.py` | 🟢 %100 |
| `scripts/import_cn_codes.py` | 🟢 %91 |
| `logging_config.py` | 🟢 %100 |
| `main.py` | 🟢 %98 |
| `pg_adapter.py` | 🟢 %96 |
| **Toplam** | **🟢 %98,33** (0,85 sn'de 197 test, eşik %80) — **hiçbir modül eşiğin dışında değil** |

13 PostgreSQL parite testi bu sayıya dahil değildir: `CUSTOMSIQ_TEST_POSTGRES_URL` gerçek bir
sunucuyu göstermedikçe atlanırlar (CI bunu tanımlar; yerel düz bir `pytest` için ne Postgres ne de
sürücü gerekir).

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
| Hiçbir kodla terim paylaşmayan açıklama | Boş liste; asla sıfır güvenli öneri değil |
| Çoğul açıklamaya karşı tekil sorgu (`cable`, `battery`) | Katlanır ve eşleşir |
| Menşe için tercihli oran mevcut | Standart MFN oranını geçersiz kılar |
| Henüz yürürlüğe girmemiş oran (`valid_from` gelecekte) | Yok sayılır; yürürlükteki orana düşülür |
| Kayıtlı oranı olmayan HS kodu | `RateNotFoundError` → HTTP `404`, asla sıfır vergi değil |
| Negatif gümrük kıymeti | `InvalidQueryError` → HTTP `400` |
| Sıfır gümrük kıymeti | Geçerli — sıfır vergi |
| Dolu veritabanının yeniden doldurulması | Idempotent — hiçbir tabloda mükerrer kayıt oluşmaz |
| Aynı classification/screening sorgusu, farklı büyük/küçük harf | Aynı `subject_reference` — hash'lemeden önce harf birleştirilir |
| Aynı vergi girdileri, farklı `customs_value` | Farklı `subject_reference` — farklı kıymet farklı karardır |
| Aynı `subject_reference` için iki inceleme kararı | İkisi de kalır, en yeni önce — denetim kayıtları asla üzerine yazılmaz |
| `POST /review`'da bilinmeyen `subject_type` veya `decision` | `InvalidQueryError` → HTTP `400` |
| Değişen açıklama/kategoriyle bir kodu yeniden içe aktarma | Eski `hs_code_history` satırı kapatılır (`valid_to` set edilir), yenisi açılır — asla silinmez |
| Aynı veriyle bir kodu yeniden içe aktarma | Yeni `hs_code_history` satırı yok; `hs_codes` zararsız bir no-op upsert alır |
| Hiç sürümlenmemiş tohumlanan bir kod için `GET /codes/{code}/history` | `200 []`, hata değil |
| Bilinmeyen bir kod için `GET /codes/{code}/history` | `HSCodeNotFoundError` → HTTP `404` |
| Taze bir veritabanında `GET /dashboard/stats` (inceleme yok, içe aktarma yok) | Tüm sayılar `0`, dağılım anahtarları eksik değil mevcut, boş listeler — frontend'de asla `NaN%` |
| Gerçek bir yaptırım eşleşmesi, aksi hâlde temiz sınıflandırma/vergi | Tarama tek başına (`0,6 × 1,0`) "yüksek"e ulaşır — diğer faktörler onu sulandıramaz |
| Yakın-ıskala + düşük sınıflandırma güveni + eksik vergi oranı birlikte | "Orta"da (`0,4989`) toplanır, hiçbiri tek başına dikkat çekici olmasa da |
| Bir risk değerlendirmesinde hiçbir kodla terim paylaşmayan açıklama | Sınıflandırma faktörü azami riski puanlar (`1,0`); vergi atlanır, "oran bulunamadı" ile karıştırılmaz |
| `/assess-risk`'e `description`/`hs_code`'dan ne biri ne ikisi verilmesi | `InvalidQueryError` → HTTP `400` |
| Risk tavanında veya üzerinde tercihli vergi oranı (testlerde sentetik %90) | Vergi faktörü `1,0`'a kırpılır, belgelenen 0–1 sözleşmesini asla aşmaz |

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

### Vergi oranları

`tariff_rates` tablosu **18 satırla** doldurulur: yukarıdaki örnekte zaten yer alan kodlar için
standart MFN oranları ve iki ticaret anlaşması kapsamındaki tercihli oranlar — bir %0 tercih ve
`valid_from` filtresinin doğru şekilde yok saydığı gelecek tarihli bir oran dahil.

| Alan | Örnek |
|---|---|
| `hs_code` | `6109100000` |
| `country_of_origin` | `NO`, `CH`, `JP`, `KR` — ya da standart MFN oranı için `ALL` |
| `rate_type` | `standard` · `preferential` |
| `rate_percent` | `12.0` · `0.0` |
| `trade_agreement` | `EU-Solvia Free Trade Agreement` · `EU-Meridian Economic Partnership` · `null` |

> 🚨 **Oranlar ve her iki ticaret anlaşması da kurgusaldır.** Gerçek vergi oranları ve tercihli
> menşeler AB TARIC veritabanından gelir; bu rakamları asla gerçek bir beyanda kullanmayın.

### Gerçek CN nomanklatürünü içe aktarma

Yukarıdaki 20 satırlık örnek bir demo veri kümesidir — **[canlı demo](https://customsiq-gs0u.onrender.com/) dahil**, orası da
bilinçli olarak mock veriyle çalışır. Tam nomanklatürle yerelde çalışmak için resmî CN referans
dosyasını indirip içe aktarın:

**1. Dosyayı edinin** (elle — içe aktarıcı ağa hiç bağlanmaz):

| Kaynak | Ne alınmalı |
|---|---|
| [Eurostat RAMON](https://ec.europa.eu/eurostat/ramon/) → *Nomenclatures* → *CN* | Güncel yılın CN'i, CSV veya Excel olarak |
| [TARIC danışma sitesi](https://ec.europa.eu/taxation_customs/dds2/taric/) | İngilizce açıklamalı eşya kodu dışa aktarımı |

**2. İçe aktarın:**

```bash
python scripts/import_cn_codes.py path/to/cn_codes.csv
```

| Seçenek | Varsayılan | Amaç |
|---|---|---|
| `--db` | `CUSTOMSIQ_DATABASE_PATH` | Hedef veritabanı; mock DB'yi bozmamak için ayrı bir dosyaya aktarın |
| `--code-column` | otomatik algılanır | Dışa aktarım alışılmadık bir başlık kullanıyorsa |
| `--description-column` | otomatik algılanır | Aynısı, açıklama sütunu için |
| `--batch-size` | `1000` | Her upsert'te yazılan satır sayısı |
| `--version-label` | bir zaman damgası | Bu çalıştırma için etiket (örn. `CN2026`), değişen her kod için kaydedilir |

İçe aktarıcı olağan RAMON/TARIC sütun adlarını otomatik algılar, her kodun kategorisini HS
bölümünden (ilk iki hane) türetir, 8 haneli yaprakların üstündeki bölüm/pozisyon satırlarını atlar,
bozuk satırları iptal etmek yerine loglayıp geçer ve **`hs_codes`'u kod üzerinden upsert yapar —
yani yeniden çalıştırmak güncel veriyi çoğaltmaz, tazeler, tıpkı öncekiyle aynı**. Yeni olan:
açıklaması veya kategorisi gerçekten değişen bir kod, `hs_code_history`'de kapatılıp yeniden
açılan bir kayıt da alır (yukarıdaki [🕘 Sürümlü CN kodları](#-sürümlü-cn-kodları-scd-type-2)
bölümüne bakın), böylece yeniden içe aktarma bir kodun eski hâlini asla sessizce kaybetmez. Bir
kodun tam zaman çizelgesini görmek için `GET /codes/{code}/history`'yi çağırın — bu aynı zamanda
demonun sürümlemeyi gösteren somut kanıtıdır.

Uygulamayı içe aktarılan veritabanına yöneltmek için:

```bash
CUSTOMSIQ_DATABASE_PATH=cn_full.db uvicorn src.customsiq.api:app
```

Excel girdisi ayrıca `pip install openpyxl` gerektirir; bilinçli olarak proje bağımlılığı değildir,
çünkü onu yalnızca bu araç kullanır. Sayfayı CSV'ye aktarmak bu ihtiyacı tamamen ortadan kaldırır.

> 📜 **Atıf.** Kombine Nomanklatür, Avrupa Birliği'nin kamuya açık referans verisidir
> (© Avrupa Birliği) ve [Komisyon'un yeniden kullanım politikası](https://ec.europa.eu/info/legal-notice_en)
> kapsamında yeniden kullanılabilir. CustomsIQ bu veriyi dağıtmaz — yukarıdaki kaynaklardan kendiniz
> indirirsiniz.

---

## 🗺️ Yol haritası

**Sekiz yeteneğin sekizi de bugün kullanıma hazır — geriye iskelet kalmadı** ve her modül kapsam
eşiğiyle ölçülüyor:

| Modül | Durum | Kapsam |
|---|---|---|
| `search.py` | ✅ **Tamamlandı** | CLI ve REST üzerinden bulanık CN kodu araması |
| `cn_classifier.py` | ✅ **Tamamlandı** | Güven skoru ve eşleşen terimlerle TF-IDF sınıflandırma |
| `embargo_screener.py` | ✅ **Tamamlandı** | CLI ve REST üzerinden yasaklı taraf isim taraması |
| `tariff_calculator.py` | ✅ **Tamamlandı** | Tercihli oran seçimiyle vergi hesaplama |
| `review.py` | ✅ **Tamamlandı** | Üç kararın tümünde dört-göz insan onayı denetim izi |
| CN kodu sürümleme (SCD Type 2) | ✅ **Tamamlandı** | `hs_code_history` + `cn_code_versions`, `GET /codes/{code}/history` üzerinden sunulur |
| `dashboard.py` | ✅ **Tamamlandı** | Faz 1 ve 2 üzerine salt-okunur raporlama, `GET /dashboard/stats` üzerinden |
| `risk.py` | ✅ **Tamamlandı** | Sınıflandırma, tarama ve vergi üzerinden toplu sevkiyat risk skoru, `GET /assess-risk` üzerinden |

Planlanan genişlemeler: ülke düzeyinde ambargo kontrolleri ve ürün/varış yeri kısıtları, kuruluş
isimleri için takma ad ile transliterasyon desteği, vergi hesabının üzerine kota/anti-damping
bileşenleri, tam CN içe aktarımı her sorgudaki yeniden kurulumu hissedilir hâle getirdiğinde
sınıflandırıcı indeksinin önbelleğe alınması, `review.py`'nin serbest metin `reviewer_name`
alanı yerine **kimlik doğrulanmış inceleyiciler + RBAC** — bu demonun gerçek hesap verebilirlik
ihtiyacı doğduğunda atılacak doğal bir sonraki adım — API uç noktasını yansıtan bir CLI
`history <code>` komutu, tam `cn_code_versions` günlüğünü sayfalayarak gezmek için ayrı bir
`GET /cn-imports` uç noktası (`/dashboard/stats` artık daha önce dışa açılmamış olan
`fetch_cn_import_runs` verisini sunuyor, ama yalnızca son birkaçını — liste tam olarak
gezilecekse özel, filtrelenebilir bir uç nokta hâlâ açık), serbest metin açıklama kabul eden bir
CLI `risk` yolu (bugün yalnızca HS kodu yoluyla sınırlı — bkz.
[⚠️ Toplu risk skorlama](#️-toplu-risk-skorlama)), ve gerçek bir dağıtımın üç kararı değil skorun
kendisini denetlemesi gerekirse kalıcı/incelenebilir risk değerlendirmeleri. Canlı dağıtımı PostgreSQL'e
yöneltmek bilinçli olarak bu listede *değil* — arka uç zaten çalışıyor (bkz. [🐘 Çift arka uç](#-çift-arka-uç-varsayılan-sqlite-isteğe-bağlı-postgres)); eksik olan, ücretsiz planda
30 günde sona ermeyen bir veritabanı.

---

## 📁 Proje yapısı

```text
CustomsIQ/
├── .github/workflows/ci.yml     # ruff → black → mypy → pytest
├── Dockerfile                   # yerel geliştirme imajı — bkz. 🐳 Docker ile çalıştırma
├── docker-compose.yml           # app + isteğe bağlı Postgres servisi (--profile postgres)
├── .dockerignore
├── requirements-runtime.txt     # requirements.txt'nin yalnızca çalışma zamanı alt kümesi, Dockerfile'da kullanılır
├── requirements-postgres.txt    # isteğe bağlı psycopg sürücüsü — bilinçli olarak requirements.txt'de DEĞİL
├── src/
│   ├── customsiq/
│   │   ├── models.py            # HSCode + SanctionedEntity + TariffRate + ReviewDecision + HSCodeVersion + ImportRun kayıtları
│   │   ├── database.py          # SQLite/Postgres katmanı + örnek veri + SCD Type 2 sürümleme
│   │   ├── pg_adapter.py        # PostgreSQL lehçe adaptörü — yalnızca URL tanımlıyken içe aktarılır
│   │   ├── matching.py          # ortak doğrulama + benzerlik skorlaması
│   │   ├── search.py            # CN kodu sıralaması
│   │   ├── cn_classifier.py     # TF-IDF sınıflandırma + gerekçe
│   │   ├── embargo_screener.py  # yaptırım isim taraması
│   │   ├── tariff_calculator.py # vergi oranı seçimi + hesaplama
│   │   ├── review.py            # insan onayı denetim izi (dört göz)
│   │   ├── dashboard.py         # Faz 1 ve 2 üzerine salt-okunur toplulaştırma
│   │   ├── risk.py              # toplu sevkiyat risk skoru
│   │   ├── exceptions.py        # tipli hata hiyerarşisi
│   │   ├── config.py            # pydantic-settings / .env
│   │   ├── logging_config.py    # ortak loglama kurulumu
│   │   ├── main.py              # CLI giriş noktası
│   │   ├── api.py               # FastAPI uygulaması (arayüzü de sunar)
│   │   └── static/index.html    # web arayüzü — tek dosya, derleme adımı yok
│   └── utils/validators.py      # CN/TARIC format ve ülke kodu doğrulaması
├── scripts/import_cn_codes.py   # resmî CN dosyası → hs_codes, değişiklikleri sürümler (SCD Type 2)
├── tests/                       # 197 test — birim, API, CLI, sınıflandırma, tarama, vergi, inceleme, içe aktarma, gösterge paneli, risk
│                                #   + sunucu tanımlı değilse atlanan 13 Postgres parite testi
│   └── fixtures/                # içe aktarıcı testleri için örnek CN dosyası
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
