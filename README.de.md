<div align="center">

# 🛃 CustomsIQ

### Compliance-Toolkit für Zoll- und Außenhandelsprozesse
**Waren unter der richtigen HS-/KN-Codenummer einreihen, Geschäftspartner gegen Sanktionslisten
prüfen und den fälligen Zoll berechnen.**

[![CI](https://github.com/Mutersec/CustomsIQ/actions/workflows/ci.yml/badge.svg)](https://github.com/Mutersec/CustomsIQ/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)
![Testabdeckung](https://img.shields.io/badge/Testabdeckung-98%25-brightgreen)
![Tests](https://img.shields.io/badge/Tests-420%20bestanden-brightgreen)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Ruff](https://img.shields.io/badge/Linting-ruff-261230?logo=ruff&logoColor=white)
![Black](https://img.shields.io/badge/Stil-black-000000)
![Mypy](https://img.shields.io/badge/typisiert-mypy-2A6DB2)
![Lizenz](https://img.shields.io/badge/Lizenz-MIT-green)

**[🌐 Live-Demo](https://customsiq-gs0u.onrender.com/)** · [📖 API-Referenz](https://customsiq-gs0u.onrender.com/docs)

<sub>Läuft auf einer kostenlosen Render-Instanz, die im Leerlauf schläft — die erste Anfrage kann ~30 s dauern.</sub>

[🇬🇧 English](README.md) · [🇹🇷 Türkçe](README.tr.md) · **🇩🇪 Deutsch**

</div>

---

> **ℹ️ Zum Demo-Datenbestand.** Der Zolltarif-Katalog der Live-Demo ist jetzt **echt**: die
> vollständige EU-Kombinierte Nomenklatur 2026, 13.753 Codes, dreisprachig (EN/DE/FR) — was das
> genau bedeutet und wie das auf Renders vergänglicher kostenloser Stufe funktioniert (im Repo
> committet, nicht live geladen — übersteht jeden Neustart ohne Netzwerkzugriff), steht unten
> unter [🌍 Die echte EU-Kombinierte Nomenklatur 2026](#-die-echte-eu-kombinierte-nomenklatur-2026).
> **Die Sanktionsliste und die Zoll-/Abgabensätze bleiben fiktive Mock-Daten** — nur der
> Produktcode-Katalog ist echt; der produktive Einsatz jedes anderen Teils dieses Tools erfordert
> weiterhin die offiziellen, in dieser README verlinkten Quellen.

---

## 📑 Inhaltsverzeichnis

| | | |
|---|---|---|
| [🎯 Problemstellung](#-problemstellung) | [✨ Funktionen](#-funktionen) | [🏗️ Architektur](#️-architektur) |
| [🧠 Designentscheidungen](#-designentscheidungen) | [⚙️ Einrichtung](#️-einrichtung) | [🚀 Verwendung](#-verwendung) |
| [🌐 API-Referenz](#-api-referenz) | [🧪 Qualität und Tests](#-qualität-und-tests) | [🌍 Die echte EU-Kombinierte Nomenklatur 2026](#-die-echte-eu-kombinierte-nomenklatur-2026) |
| [🗺️ Roadmap](#️-roadmap) | [📁 Projektstruktur](#-projektstruktur) | [📄 Lizenz](#-lizenz) |

---

## 🎯 Problemstellung

Die Zuordnung der korrekten **KN-Codenummer** (der EU-*Kombinierten Nomenklatur*, die den
internationalen HS-Code auf 8 Stellen und im TARIC auf 10 Stellen erweitert) gehört zu den
langsamsten und fehleranfälligsten Schritten einer Zollanmeldung. Heute geschieht sie manuell —
anhand eines Zolltarifs mit Zehntausenden von Zeilen.

| Schwachstelle | Betriebswirtschaftliche Folge |
|---|---|
| 🔍 Manuelle Suche in einem riesigen Zolltarif | Langsame Anmeldungen; das Ergebnis hängt davon ab, wer gerade Schicht hat |
| ❌ Fehlerhafte Tarifierung | Falscher Zollsatz, Bußgelder, festgehaltene Sendungen |
| 🧠 Wissen steckt in den Köpfen Einzelner | Lange Einarbeitung, keine prüffähige Begründung für den gewählten Code |

**CustomsIQ automatisiert den ersten Durchgang:** Sie geben eine alltagssprachliche
Produktbeschreibung ein und erhalten eine nach Ähnlichkeitswert sortierte Vorauswahl an
Tarifnummern — ein Ausgangspunkt, den eine Fachkraft bestätigt, und keine Blackbox, die allein
entscheidet.

---

## ✨ Funktionen

| | Funktion | Beschreibung |
|---|---|---|
| 🔍 | **Unscharfe Suche** | Freitextbeschreibung → nach Ähnlichkeitswert sortierte KN-/TARIC-Codes |
| 🧠 | **Code-Einreihung** | TF-IDF-Vorschläge mit Konfidenzwert und den ausschlaggebenden Begriffen |
| 🚫 | **Sanktionsprüfung** | Name → Treffer auf Verbotslisten, tolerant gegenüber Wortstellung und Teilnamen |
| 💶 | **Zollberechnung** | Code + Ursprung + Wert → fälliger Zoll, mit Satz und Begründung |
| 📋 | **Prüfprotokoll (Vier-Augen-Prinzip)** | Klassifizierung, Prüfung oder Zollergebnis freigeben/ablehnen/markieren — nur Anhängen |
| 🕘 | **Versionierte KN-Codes (SCD Type 2)** | Jede geänderte Beschreibung/Kategorie behält ihren vorherigen Wert, mit Zeitstempel — `GET /codes/{code}/history` |
| 📊 | **Analyse-Dashboard** | Schreibgeschützter Überblick über Referenzdaten, Prüfaktivität und Importläufe — `GET /dashboard/stats` |
| ⚠️ | **Zusammengesetztes Risiko-Scoring** | Ein erklärbarer Score aus Einreihungskonfidenz, Prüfung und Zoll — `GET /assess-risk` |
| 🖥️ | **Weboberfläche** | Single-Page-Frontend unter `/` — ohne Build-Schritt, Framework oder CDN |
| 📥 | **Import echter Daten** | Lädt die offizielle EU-KN-Nomenklatur aus einer lokalen Datei, versioniert Änderungen |
| 💻 | **Interaktive CLI** | Codes suchen oder `screen <Name>` am selben Prompt ausführen |
| 🌐 | **REST-API** | `GET /search` und `GET /screen` über FastAPI, mit erzeugter `/docs`-Oberfläche |
| 🗄️ | **Speicherung ohne Einrichtungsaufwand** | SQLite aus der Standardbibliothek, vorbefüllt mit 20 Codes + 18 fiktiven Einträgen |
| 🧩 | **SAP-GTS-Terminologieansicht** | Stellt Ergebnisse im SAP-GTS-Vokabular und in BAPIRET2-Form dar — eine gekennzeichnete Simulation, keine Systemanbindung |
| 📄 | **Rechnungsauslesung** | Ein Rechnungs-PDF hochladen und die Einreihungs-, Zoll- und Risikoformulare kommen vorausgefüllt zurück — Text-PDFs, reines Python, nichts wird gespeichert |
| 🔐 | **RBAC** | Vier Rollen über echte Konten — Sanktionsfreigaben brauchen einen Compliance-Officer, und das Prüfprotokoll nennt die Sitzung, nicht ein Textfeld |
| 🐘 | **Zwei Backends** | Dasselbe SQL läuft auch auf PostgreSQL — per Umgebungsvariable zuschaltbar, Standard bleibt SQLite |
| ⚙️ | **Konfiguration über Umgebung** | `pydantic-settings` liest `.env` — keine fest codierten Pfade oder Schwellenwerte |
| 🚨 | **Typisierte Fehler** | `InvalidQueryError`, `HSCodeNotFoundError` → saubere HTTP-`400`/`404`-Semantik |
| 🧪 | **Erzwungene Qualität** | ruff + black + mypy + 98 % Testabdeckung, bei jedem Push in der CI geprüft |

---

## 🏗️ Architektur

Zwei Funktionen — **KN-Code-Suche** und **Sanktionsprüfung** — setzen auf einer gemeinsamen
Matching-Schicht auf. CLI und HTTP-API sind dünne Adapter über `search()` und `screen_entity()`;
Scoring- und Validierungslogik existiert an genau einer Stelle und wird nie dupliziert.

```mermaid
flowchart LR
    subgraph Schnittstellen
        CLI["💻 main.py<br/>Interaktive CLI"]
        API["🌐 api.py<br/>FastAPI /search · /classify<br/>· /screen · /calculate-duty · /review<br/>· /codes/{code}/history · /dashboard/stats<br/>· /assess-risk"]
        IMPORT["📥 import_cn_codes.py<br/>CLI-Importwerkzeug"]
    end

    SEARCH["🔍 search.py<br/>KN-Codes ranken"]
    CLS["🧠 cn_classifier.py<br/>TF-IDF + Begründung"]
    SCREEN["🚫 embargo_screener.py<br/>Sanktionstreffer ranken"]
    DUTY["💶 tariff_calculator.py<br/>Satzwahl + Berechnung"]
    REVIEW["📋 review.py<br/>Entscheidungen speichern + abrufen"]
    DASH["📊 dashboard.py<br/>aggregierte Statistiken"]
    RISK["⚠️ risk.py<br/>Gesamtbewertung"]
    MATCH["🧩 matching.py<br/>Validierung + Ähnlichkeit"]
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
    DUTY -. löst aus .-> EXC
    MATCH -. löst aus .-> EXC
    DB -. löst aus .-> EXC
    REVIEW -. löst aus .-> EXC
    CFG --> CLI
    CFG --> API
    CFG --> SCREEN
```

### Zuständigkeiten der Module

| Modul | Zuständigkeit |
|---|---|
| `models.py` | `HSCode`, `SanctionedEntity`, `TariffRate`, `ReviewDecision`, `HSCodeVersion` und `ImportRun` — die unveränderlichen Datensätze |
| `database.py` | SQLite-Schema, Verbindung, Beispieldaten, `fetch_all*()`, `get_by_code()`, `upsert_hs_codes_with_history()` (SCD Type 2) |
| `matching.py` | Eingabevalidierung + Ähnlichkeitsbewertung (**von beiden Funktionen genutzt**) |
| `search.py` | Rankt KN-Codes nach Beschreibungsähnlichkeit |
| `cn_classifier.py` | Schlägt Codes über TF-IDF-Gewichtung vor und nennt die passenden Begriffe |
| `embargo_screener.py` | Rankt Sanktionslistentreffer nach Namensähnlichkeit |
| `tariff_calculator.py` | Wählt den anwendbaren Zollsatz und berechnet den fälligen Betrag |
| `review.py` | Speichert und listet menschliche Freigaben zu vergangenen Entscheidungen (Prüfprotokoll) |
| `dashboard.py` | Schreibgeschützte Aggregation von Referenzdaten, Prüfaktivität und KN-Importen für `/dashboard/stats` |
| `risk.py` | Kombiniert classify/screen/duty zu einem erklärbaren zusammengesetzten Risiko-Score |
| `exceptions.py` | `CustomsIQError` → `InvalidQueryError`, `HSCodeNotFoundError`, `RateNotFoundError` |
| `config.py` | `pydantic-settings`; liest `CUSTOMSIQ_*`-Umgebungsvariablen und `.env` |
| `logging_config.py` | Gemeinsames Logging — schlichtes Format nach stdout, nirgends ein `print()` |
| `main.py` | Einstiegspunkt der interaktiven CLI (Suche + `screen <Name>`) |
| `api.py` | FastAPI-Anwendung: liefert das Frontend unter `/`, dazu `/search`, `/classify`, `/screen`, `/calculate-duty`, `/review`, `/review/history`, `/codes/{code}/history`, `/dashboard/stats`, `/assess-risk`, `/health` |
| `scripts/import_cn_codes.py` | CLI-Importwerkzeug: parst einen KN-Export und versioniert Änderungen über `upsert_hs_codes_with_history()` |
| `static/index.html` | Das gesamte Frontend — Inline-CSS, reines `fetch()`, keine Abhängigkeiten |

### Datenmodell

```sql
CREATE TABLE hs_codes (
    code        TEXT PRIMARY KEY,   -- z. B. "6109100000"
    description TEXT NOT NULL,      -- z. B. "Cotton T-shirts, knitted"
    category    TEXT NOT NULL       -- z. B. "Textile"
);

CREATE TABLE sanctioned_entities (
    name        TEXT PRIMARY KEY,   -- z. B. "Northwind Maritime Holdings Ltd"
    country     TEXT NOT NULL,      -- ISO 3166-1 alpha-2, z. B. "CY"
    list_source TEXT NOT NULL,      -- z. B. "EU Consolidated Financial Sanctions List"
    date_added  TEXT NOT NULL       -- ISO-8601-Datum, z. B. "2023-04-12"
);

CREATE TABLE tariff_rates (
    hs_code           TEXT NOT NULL,  -- z. B. "6109100000"
    country_of_origin TEXT NOT NULL,  -- ISO alpha-2, oder "ALL" für den Regelsatz (MFN)
    rate_type         TEXT NOT NULL,  -- "standard" oder "preferential"
    rate_percent      REAL NOT NULL,  -- z. B. 12.0
    trade_agreement   TEXT,           -- NULL bei Regelsätzen
    valid_from        TEXT NOT NULL,  -- ISO-8601-Datum des Inkrafttretens
    PRIMARY KEY (hs_code, country_of_origin, valid_from)
);

CREATE TABLE review_decisions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,  -- Prüfdatensätze haben keinen natürlichen Schlüssel
    subject_type       TEXT NOT NULL,   -- "classification" | "screening" | "duty"
    subject_reference  TEXT NOT NULL,   -- sha256(subject_type + normalisierte Eingabe)
    decision           TEXT NOT NULL,   -- "approved" | "rejected" | "flagged"
    reviewer_name      TEXT NOT NULL,   -- der authentifizierte Benutzername (API) oder Freitext (CLI/vor RBAC)
    comment            TEXT,            -- optionale Notiz
    reviewed_at        TEXT NOT NULL    -- ISO-8601-Zeitstempel
);

-- Wer freigegeben hat, sofern das ein authentifiziertes Konto war. Eine
-- Prüfzeile ohne Eintrag hier wurde ohne Authentifizierung geschrieben (CLI,
-- oder bevor es Konten gab) und wird auch so ausgewiesen. Verknüpft über die
-- Zeilen-ID, nie über den Namen: ein historisches "alice" kann damit niemand
-- für sich reklamieren, indem er sich später so registriert. Eine eigene
-- Tabelle statt einer Spalte an review_decisions, aus demselben Grund wie bei
-- hs_code_history: CREATE TABLE IF NOT EXISTS ändert eine bestehende Datenbank nie.
CREATE TABLE review_authorship (
    review_id  INTEGER PRIMARY KEY,  -- die review_decisions-Zeile
    user_id    INTEGER NOT NULL      -- der authentifizierte Urheber
);

CREATE TABLE users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT NOT NULL UNIQUE,  -- beim Anlegen kleingeschrieben
    password_hash  TEXT NOT NULL,         -- pbkdf2_sha256$<Iterationen>$<Salt>$<Hash>
    role           TEXT NOT NULL,         -- viewer | analyst | compliance_officer | admin
    created_at     TEXT NOT NULL
);

CREATE TABLE sessions (
    token_hash  TEXT PRIMARY KEY,  -- SHA-256 des Tokens; das Token selbst wird nie gespeichert
    user_id     INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL      -- beim Lesen geprüft, daher wirken Abmeldung und Ablauf sofort
);

CREATE TABLE hs_code_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,  -- Historieneinträge haben keinen natürlichen Schlüssel
    code          TEXT NOT NULL,     -- der hs_codes.code, zu dem diese Version gehört
    description   TEXT NOT NULL,     -- die Beschreibung während der Gültigkeit dieser Version
    category      TEXT NOT NULL,     -- die Kategorie während der Gültigkeit dieser Version
    valid_from    TEXT NOT NULL,     -- ISO-8601-Zeitstempel, ab dem diese Version aktuell wurde
    valid_to      TEXT,              -- ISO-8601-Zeitstempel der Ablösung, NULL wenn noch aktuell
    version_label TEXT NOT NULL      -- der Importlauf, der diese Version erzeugt hat, z. B. "CN2026"
);

CREATE TABLE cn_code_versions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    version_label       TEXT NOT NULL,     -- z. B. "CN2026"
    source_description  TEXT,              -- z. B. der Name der importierten Datei
    imported_at         TEXT NOT NULL,     -- ISO-8601-Zeitstempel des Laufabschlusses
    row_count           INTEGER NOT NULL   -- in diesem Lauf verarbeitete KN-Blattcodes
);
```

---

## 🧠 Designentscheidungen

### Warum `difflib` statt `rapidfuzz` / `thefuzz`?

`difflib.SequenceMatcher` ist Teil von Python. Das bedeutet **keine zusätzliche Abhängigkeit**,
nichts zu pinnen oder sicherheitstechnisch zu prüfen, keine Installationshürde — und es genügt beim
derzeitigen Datenvolumen vollkommen.

| | `difflib` *(gewählt)* | `rapidfuzz` |
|---|---|---|
| **Abhängigkeit** | ✅ Standardbibliothek | ⚠️ Drittanbieter + C-Erweiterung |
| **Geschwindigkeit bei ~10² Zeilen** | ✅ Nicht wahrnehmbar | ✅ Nicht wahrnehmbar |
| **Geschwindigkeit bei ~10⁵ Zeilen** | ❌ Spürbar langsam | ✅ C-optimiert, deutlich schneller |
| **Toleranz gegenüber Wortstellung** | ❌ Nur positionsbasierter Abgleich | ✅ `token_sort`- / `token_set`-Scorer |
| **Durchsatz bei Massenverarbeitung** | ❌ Reines Python | ✅ `process.extract`, mehrkernfähig |

### 🔀 Wann der Wechsel ansteht

Ersetzen Sie `similarity()` in `matching.py` durch `rapidfuzz.fuzz.WRatio`, sobald **einer** dieser
Punkte zutrifft:

1. **📈 Datenvolumen** — der reale Zolltarif (Zehntausende Zeilen) macht den linearen Durchlauf messbar langsam.
2. **🔤 Wortstellung** — Abfragen wie *„Hose Baumwolle Herren“* sollen *„Men's cotton trousers“* treffen; positionsbasierter Abgleich leistet das schlecht.
3. **⚡ Durchsatz** — ein Stapellauf zur Neutarifierung benötigt Tausende Abfragen pro Sekunde.

> Der Austausch beschränkt sich auf **eine einzige Funktion**. Die Entscheidung bleibt damit
> günstig und lässt sich später treffen — sie ist keine Festlegung, die heute nötig wäre.

### Weitere bewusste Entscheidungen

| Entscheidung | Begründung | Ausbaupfad |
|---|---|---|
| **Standardmäßig SQLite, optional PostgreSQL** | Referenzdaten auf einem Knoten, überwiegend lesend; kein Betriebsaufwand. Die Verbindungsschicht spricht jetzt beides — `CUSTOMSIQ_DATABASE_URL` wechselt das Backend, ohne ein Modul anzufassen | PostgreSQL zum Standard machen, sobald mehrere Schreiber oder dauerhaft gehosteter Zustand nötig werden |
| **Eine gemeinsame Verbindung** mit `check_same_thread=False` | Einfach und mit dem Threadpool von FastAPI verträglich | Verbindungspool, sobald parallele Schreibzugriffe auftreten |
| **Logging statt `print()`** | Derselbe Ausgabeweg für CLI und API; Level über die Konfiguration steuerbar | — |
| **Validierung in `matching.py`** | Suche, Prüfung, CLI und API erben sie; ein neuer Aufrufer kann sie nicht versehentlich umgehen | — |
| **Kein `EmbargoScreeningError`** | Die Eingabevalidierung der Prüfung ist identisch mit der der Suche, daher wird `InvalidQueryError` wiederverwendet statt eine Klasse zu duplizieren | Ergänzen, sobald die Prüfung einen wirklich eigenen Fehlerfall bekommt |
| **`review_decisions` nutzt `INTEGER PRIMARY KEY AUTOINCREMENT`**, anders als die anderen drei Tabellen | Prüfdatensätze sind nicht von Natur aus eindeutig — dieselbe `subject_reference` kann im Lauf der Zeit mehrere Entscheidungen erhalten | — |
| **`review_decisions` ist nur anhängend (append-only)** | Modelliert das Vier-Augen-/Freigabeprinzip, wie es in Compliance-Tools wie SAP GTS üblich ist: eine korrigierte Entscheidung ist eine neue Zeile, keine Bearbeitung, sodass der Verlauf nie verloren geht. `reviewer_name` ist jetzt für alles über die API Eingereichte das authentifizierte Konto (siehe [🔐 Authentifizierung](#-authentifizierung-ohne-abhängigkeit)); CLI-Zeilen und Zeilen von vor RBAC behalten ihren Freitext und werden als nicht authentifiziert gekennzeichnet statt umgedeutet | Konten an einen externen Identity Provider (SSO/SCIM) binden statt an lokale Passwörter |
| **KN-Code-Historie liegt in einer separaten `hs_code_history`-Tabelle**, nicht in `valid_from`/`valid_to`-Spalten auf `hs_codes` selbst | `hs_codes` behält sein bestehendes `code TEXT PRIMARY KEY` und seine beiden Lesefunktionen (`fetch_all`, `get_by_code`) bleiben byte-für-byte unverändert — nichts zu filtern, nichts zu vergessen. Es ist zudem die einzige migrationssichere Option: Dieses Projekt hat keine Schema-Migrationen, und `CREATE TABLE IF NOT EXISTS` ändert nie eine bestehende Tabelle, also würden Spalten auf `hs_codes` in keiner bestehenden `customsiq.db`-Datei je erscheinen | Bei einem Produktivbetrieb, der von Tag eins volle Historientiefe braucht, eine einmalige Eröffnungszeile pro bestehendem Code nachträglich befüllen |

### 🕘 Versionierte KN-Codes (SCD Type 2)

Das erneute Importieren von KN-Referenzdaten überschrieb `hs_codes` bisher stillschweigend an Ort
und Stelle (`ON CONFLICT DO UPDATE`) — wurde eine Einreihungs- oder Zollentscheidung gegen eine
alte Beschreibung getroffen und die Nomenklatur später mit geänderten Daten neu importiert, gab es
keine Möglichkeit zu rekonstruieren, was das System zum Entscheidungszeitpunkt "wusste".
`scripts/import_cn_codes.py` versioniert jetzt jede tatsächliche Änderung nach dem in
BI-/Data-Warehouse-Werkzeugen gängigen SCD-Type-2-Muster (dieselbe Idee wie SAP BWs
Änderungsbeleg-Tabellen): `hs_codes` hält weiterhin genau eine aktuelle Zeile pro Code, exakt wie
zuvor, während `hs_code_history` jeden vorherigen Wert aufbewahrt — geschlossen, nicht gelöscht.

Import von "CN2025" (ein neuer Code), dann "CN2026" (derselbe Code, Beschreibung überarbeitet):

| Tabelle | Nach CN2025 | Nach CN2026 |
|---|---|---|
| `hs_codes` | `6109100000` → *"Cotton T-shirts, knitted"* | `6109100000` → *"Cotton T-shirts, knitted or crocheted"* (alter Wert hier weg, genau wie bisher) |
| `hs_code_history` | eine offene Zeile: *"...knitted"*, `valid_to = NULL`, `version_label = "CN2025"` | diese Zeile jetzt **geschlossen** (`valid_to` gesetzt) **plus eine neue offene Zeile**: *"...knitted or crocheted"*, `version_label = "CN2026"` |
| `cn_code_versions` | `CN2025`, `row_count = 1` | `CN2026`, `row_count = 1` |

`GET /codes/6109100000/history` liefert beide `hs_code_history`-Zeilen, älteste zuerst — die alte
Beschreibung bleibt erhalten, sie wird nicht gelöscht. Ein erneuter Import von "CN2026" mit
**identischen** Daten fügt keiner der beiden Historientabellen etwas hinzu: nur `cn_code_versions`
protokolliert, dass der Lauf stattgefunden hat, mit 0 Änderungen. `search.py`, `cn_classifier.py`,
`tariff_calculator.py` und `embargo_screener.py` bleiben davon unberührt — `tariff_calculator.py`
liest `hs_codes` überhaupt nicht, die anderen beiden rufen ohnehin nur `fetch_all()` auf, das genau
das liefert, was es immer geliefert hat.

Das stärkt zudem das Prüfprotokoll der Freigabeschicht: `review_decisions` erfasst, *dass* eine
Entscheidung geprüft wurde, und die KN-Code-Historie macht es nun möglich zu rekonstruieren,
welche Nomenklaturdaten zu diesem Zeitpunkt aktiv waren.

### 📊 Dashboard: die Berichtsschicht über Phase 1 & 2

`dashboard.py` fügt keine neue Geschäftslogik hinzu und trifft keine Entscheidungen — es ist eine
schreibgeschützte Aggregation dessen, was `review.py` und die KN-Pipeline bereits erfasst haben,
und setzt bestehende `database.py`-Lesevorgänge (`fetch_all`, `fetch_all_entities`,
`fetch_review_decisions`, `fetch_cn_import_runs`, plus zwei kleine neue Zählprimitive) zu einem
einzigen `GET /dashboard/stats`-Aufruf für das Dashboard-Panel des Frontends zusammen. Eine
Anpassung ist erwähnenswert: `cn_code_versions` (Phase 2) speicherte immer nur `row_count` pro
Importlauf, keine Aufschlüsselung nach neu/geändert/unverändert — diese Aufschlüsselung existierte
nur vorübergehend innerhalb von `upsert_hs_codes_with_history()` und wurde nie persistiert. Anstatt
nachträglich Spalten dafür hinzuzufügen, leitet das Dashboard **geändert vs. unverändert** pro Lauf
davon ab, wie viele `hs_code_history`-Zeilen das `version_label` dieses Laufs tragen (eine einzige
`GROUP BY`-Abfrage, nicht drei separate Zählungen) — eine ehrliche Lesart dessen, was tatsächlich
erfasst wurde, keine erfundene Aufschlüsselung.

### ⚠️ Zusammengesetztes Risiko-Scoring

Echte risikobasierte Zollkontrollen (SAP GTS Compliance Management eingeschlossen) bewerten
Einreihung, Prüfung und Zoll nicht unabhängig voneinander — das Gesamtrisiko einer Sendung ist
eine Funktion aller drei zusammen. `risk.py` fügt `assess_shipment()` hinzu, das `classify()`,
`screen_entity()` und `calculate_duty()` aufruft — deren bestehende öffentliche Signaturen, ohne
Neuerungen — und die drei zu einem Gesamtscore zusammenführt:

```
gesamt = 0,6 × Prüfung + 0,25 × Einreihung + 0,15 × Zoll      (jeder Faktor in [0, 1])
Stufe = "hoch" wenn gesamt ≥ 0,5, "mittel" wenn ≥ 0,2, sonst "niedrig"
```

| Faktor | Gewicht | Regel | Warum |
|---|---|---|---|
| **Prüfung** | 0,6 | Echter Treffer → `1,0`; Beinahe-Treffer (ein Treffer nur bei einem niedrigeren Beobachtungsschwellenwert von 0,55 gegenüber dem Compliance-Schwellenwert von 0,75) → `0,4`; nichts → `0,0` | Ein echter Treffer ist disqualifizierend, nicht nur riskant — bei einem Gewicht von 0,6 überschreitet ein Treffer allein (`0,6`) bereits "hoch", egal wie sauber die anderen beiden Faktoren sind |
| **Einreihung** | 0,25 | `1 − höchste_Konfidenz`; kein Treffer → `1,0`; Code direkt angegeben (nichts abzuleiten) → `0,0` | Niedrige Konfidenz bedeutet, dass der falsche HS-Code angewendet werden könnte — ein Datenqualitätsproblem, kein Compliance-Verstoß, daher deutlich unter dem Gewicht der Prüfung |
| **Zoll** | 0,15 | `min(Zollsatz / 20, 1,0)`, `+0,15` bei Präferenzsatz, auf `1,0` begrenzt; fehlender Satz → fest `0,6` | 20 % liegt über jedem eingesäten Regelsatz (16,9 %, Schuhwerk, ist der höchste); der Präferenzbonus spiegelt einen realen Betrugsvektor wider — ein Freihandelsabkommen-Anspruch wird bei einer Prüfung genau deshalb erneut verifiziert, selbst bei einem niedrigen oder Nullsatz |

Zwei Dinge, die explizit gemacht werden, nicht implizit bleiben:

- **Der Zollfaktor wird begrenzt**, `min(min(Zollsatz/20, 1) + 0,15, 1,0)`, nicht nur
  unbegrenztes `+ 0,15`. Nichts im Datenmodell begrenzt `TariffRate.rate_percent`, sodass ein
  Präferenzsatz an oder über der 20-%-Obergrenze eine reale Möglichkeit ist, die das Schema
  zulässt, auch wenn die heutigen Seed-Daten zufällig keinen solchen enthalten — die Begrenzung
  ist nach den Bedingungen des Datenmodells korrekt, nicht nur nach den heutigen Fixtures, und
  wird durch einen dedizierten Test mit einem synthetischen 90-%-Satz abgedeckt.
- **Kein Prüfprotokoll-Eintrag.** Eine Risikobewertung wird nicht persistiert und ist nicht über
  `review_decisions` prüfbar — eine Neuberechnung ist günstig (drei bestehende Funktionsaufrufe,
  keine neue I/O), und sie prüfbar zu machen würde bedeuten, `review.py`s geschlossene
  `_VALID_SUBJECT_TYPES`-Menge zu erweitern, die diese Phase bewusst nicht anfasst. Eine
  Risikobewertung ist ohnehin keine neue Art von Entscheidung — sie ist eine Linse über die drei
  Entscheidungen, die bereits prüfbar sind, und sagt einem Prüfer, *welche* der drei zuerst
  anzusehen ist, statt ein viertes Ding zum Freigeben oder Ablehnen hinzuzufügen.

`InvalidQueryError` aus einem der drei zugrunde liegenden Aufrufe (ein fehlerhafter HS-Code, ein
falsches Land, ein negativer Wert) wird nie abgefangen und in einen Score umgewandelt — eine
schlechte Eingabe ist ein Anfrageproblem und erscheint als HTTP `400`, genau wie bei jedem
anderen Endpunkt. Der CLI-Befehl `risk` unterstützt nur den HS-Code-Pfad, keine
Freitextbeschreibung: Eine flache REPL-Zeile kann nicht eindeutig zwei separate Freitextfelder
(Beschreibung und Parteiname) enthalten — anders als `duty <code> <land> <wert>` und
`screen <name>`, die jeweils eines enthalten können. API und Frontend (strukturierte
Formularfelder) unterstützen beides.

### ☁️ Was RBAC auf Render braucht: nichts

**Damit die Anmeldung in der Live-Demo funktioniert, ist keine neue Umgebungsvariable
nötig, und an `requirements.txt` hat sich nichts geändert** — Renders Build ist also
identisch mit dem vor dieser Phase, und im Dashboard ist nichts zu tun. Das folgt direkt
aus dem Sitzungsentwurf: undurchsichtige, in der Datenbank abgelegte Tokens brauchen
keinen Signaturschlüssel, es gibt also keinen `SECRET_KEY` zum Setzen, Rotieren oder
Verlieren. (Ein JWT oder Starlettes Middleware mit signierten Cookies hätte genau so eine
Variable verlangt, bevor die Anmeldung live überhaupt funktioniert hätte.)

Zwei ehrliche Einschränkungen, beide Folge des ohnehin dokumentierten kostenlosen Tarifs:

- **Konten sind flüchtig.** Das Dateisystem wird zurückgesetzt, Registrierungen und
  Rollenwechsel verschwinden beim Neustart, die Demo-Konten werden neu angelegt — genau
  das Verhalten, das die übrigen eingesäten Daten schon haben. Verwenden Sie hier kein
  echtes Passwort.
- **`Secure` am Session-Cookie ist abgeleitet, nicht fest verdrahtet**, nämlich aus
  `X-Forwarded-Proto` (Render terminiert TLS an einem Proxy, die App selbst sieht reines
  HTTP). Fest verdrahtet hätte es `http://localhost` zerstört; ignoriert hätte es das
  Cookie im Klartext verschickt.

Wie nach Phase 5 und 6 lohnt genau eine menschliche Kontrolle: dass Runtime und
Build-Befehl des Dienstes unverändert sind. Nichts hier sollte sie berührt haben.

### 🐳 Docker für die lokale Entwicklung, nicht für Render (noch nicht)

Ein `Dockerfile` zu einem Repo hinzuzufügen, dessen Render-Service nie mit einem konfiguriert
war, ist genau die Art von Änderung, die es wert ist, vor und nicht nach dem Handeln durchdacht
zu werden — Render *kann* aus einem `Dockerfile` bauen, wenn die Language eines Services auf
Docker gesetzt ist, und das falsch zu machen könnte bedeuten, dass die Live-Demo anders baut/
startet als heute. Vor dem Schreiben von irgendetwas gegen Renders eigene Dokumentation
recherchiert: Docker zu aktivieren wird als eine Dashboard-Einstellung zum **Zeitpunkt der
Service-Erstellung** beschrieben (*"wenden Sie die folgenden Einstellungen im Render Dashboard
bei der Service-Erstellung an: 1. Setzen Sie das Feld Language auf Docker"*) — es gibt keinen
dokumentierten Mechanismus, mit dem ein *bereits erstellter* Service seine Runtime neu erkennt
und wechselt, weil in einem späteren Push ein `Dockerfile` auftaucht. Dieses Repo hat außerdem
weder `render.yaml` noch Procfile, was bestätigt, dass die Build-/Start-Befehle und die Runtime
des Live-Service vollständig in Renders Dashboard leben, außerhalb dieses Repos — das Pushen von
Dateien hierher kann das nicht überschreiben.

Angesichts dessen liegen `Dockerfile`/`docker-compose.yml` im Repo-Root (der konventionelle Ort)
statt in einem Unterverzeichnis versteckt, um einem Erkennungsmechanismus auszuweichen, der laut
obiger Recherche auf einen bereits bestehenden Service ohnehin nicht zutrifft. Die eine Sache,
die einen einmaligen menschlichen Blick wert ist: das Render-Dashboard für diesen Service öffnen
und bestätigen, dass Language/Runtime noch auf der heutigen nativen Einstellung steht, nicht auf
"Docker" — angesichts der obigen Begründung eine kostenlose Bestätigung, kein erwartetes
Problem, da ich dieses Dashboard nicht selbst einsehen kann, um es direkt zu verifizieren.

### 🧵 Eine geteilte SQLite-Verbindung, jetzt wirklich threadsicher

Beim Bau dieser Phase gefunden, und festhaltenswert, weil das Symptom alarmierend war und
die Ursache lange vor RBAC schlummerte: die App hält **eine** SQLite-Verbindung pro
Prozess, und FastAPI führt synchrone Routen in einem Threadpool aus — mehrere Requests
fassen dieses Objekt also tatsächlich gleichzeitig an. `check_same_thread=False` bringt
nur Pythons Wächter zum Schweigen, macht das Teilen aber nicht sicher. Das SQLite dieses
Rechners ist mit `SQLITE_THREADSAFE=2` übersetzt (Multi-Thread: eine Verbindung pro
Thread), und Python meldet `sqlite3.threadsafety == 1` — Threads dürfen das Modul teilen,
eine Verbindung aber **nicht**.

Vor dieser Phase ging das gut, weil gleichzeitige Datenbankarbeit selten war. RBAC legte
auf *jeden* Request eine Sitzungsabfrage, und aus dem latenten Rennen wurde der Normalfall:
erst ein verstümmelter Lesevorgang (`Could not decode to UTF-8 column 'username'`), dann
ein Segfault — ein `SIGSEGV`, der den Server mitten in der Anmeldung mitnahm.

Die Lösung ist ein per Lock geschützter Wrapper (`database._SerializedConnection`), in
derselben Form, die `pg_adapter.PgConnection` für PostgreSQL bereits nutzt: jedes Statement
läuft unter einem Lock, und seine Zeilen werden **geholt, bevor das Lock freigegeben wird** —
einen lebenden Cursor zurückzugeben hätte den unsicheren Lesevorgang nach draußen verlagert
und nichts behoben. Ein Regressionstest schickt 24 parallele angemeldete Request-Runden
durch einen Threadpool; ohne den Wrapper reproduziert er den Segfault, die Absicherung ist
also verifiziert und nicht bloß angenommen. Der PostgreSQL-Pfad bleibt unberührt (psycopg
regelt das selbst).

### 🐘 Zwei Backends: SQLite als Standard, PostgreSQL optional

PostgreSQL kam *neben* SQLite dazu, nicht an dessen Stelle — und die Begründung ist eine
Kostenrechnung, keine Geschmacksfrage.

**Warum kein vollständiger Wechsel.** Die gesamte Suite läuft gegen `:memory:` in deutlich unter
einer Sekunde, ohne Server und ohne Treiber; ein vollständiger Wechsel würde jeden lokalen
`pytest`-Lauf von einem laufenden PostgreSQL (oder testcontainers) abhängig machen — für Code,
dessen Verhalten auf beiden Backends identisch ist. Die Live-Demo gewinnt ebenfalls nichts: Sie
liefert bewusst fiktive Daten mit schnellen Kaltstarts auf einem Dateisystem, das zurückgesetzt
wird; das erneute Einsäen ist Teil des Entwurfs, kein Mangel, den PostgreSQL beheben würde. Und
die Hosting-Kosten sind real: **Renders kostenlose PostgreSQL-Datenbank läuft 30 Tage nach
Erstellung ab** (danach nur mit kostenpflichtigem Plan erreichbar, 14 Tage Karenz vor der
endgültigen Löschung, eine freie Datenbank pro Workspace, 1 GB) —
[Render-Doku](https://render.com/docs/free). Ein Portfolio-Link, der jeden Monat still kaputtgeht,
ist schlechter als einer, der einfach online bleibt. Ein SQL-Satz auf zwei Backends zeigt zudem
mehr als die Wahl eines einzelnen: dass die Datenschicht wirklich abstrahiert ist.

**Warum ein ~150-Zeilen-Adapter und nicht SQLAlchemy Core.** Derselbe Test wie bei `openpyxl` und
scikit-learn: Beseitigt die Abhängigkeit das Problem, für das sie gedacht ist? Nein. Der härteste
Dialektunterschied hier — `ON CONFLICT … DO UPDATE` — ist auf beiden Backends *identisch*, während
Cores Upsert dialektspezifisch ist (`dialects.postgresql.insert` vs. `dialects.sqlite.insert`); die
Fallunterscheidung bliebe also ohnehin. Dafür würde Core alle ~18 Statements des SQLite-Pfads
umschreiben — genau des Pfads, den die Live-Seite ausführt — und einen neuen Import in jeden
Standard-Testlauf bringen. `src/customsiq/pg_adapter.py` wird lazy importiert, nur im
PostgreSQL-Zweig von `get_connection`, sodass `psycopg` ein optionales Extra bleibt. Seine Grenze
steht im Quelltext: Die Übersetzung `?` → `%s` ist ein naives Ersetzen, tragfähig solange kein
Statement ein literales `?` oder `%` enthält (ein Test prüft alle durch); darüber hinaus sqlglot
oder Core statt weiterer Regexes.

**Was tatsächlich abweicht — gegen einen echten `postgres:16`-Container verifiziert, nicht
angenommen:**

| | SQLite | PostgreSQL | Behandlung |
|---|---|---|---|
| Platzhalter | `?` | `%s` | im Adapter übersetzt |
| `id`-Spalten | `INTEGER PRIMARY KEY AUTOINCREMENT` | kein Äquivalent | zu `GENERATED ALWAYS AS IDENTITY` umgeschrieben |
| `rate_percent REAL` | 8-Byte-Float | **4-Byte-`float4`** — `16.9` kommt als `16.899999618…` zurück | zu `DOUBLE PRECISION`; ein Test prüft exakt `== 16.9` |
| Neue Zeilen-ID | `cursor.lastrowid` | in psycopg nicht vorhanden | `… RETURNING id` nur auf PostgreSQL; der SQLite-Pfad behält seine bisherige Abfolge exakt |
| `FROM (SELECT …)` | Alias optional | vor PG 16 zwingend | `AS changed_codes` ergänzt (auf beiden gültig) |
| Mehrteiliges `SCHEMA` | `executescript` | keine solche Methode | der Adapter teilt auf und führt jedes Statement aus |
| Text-`ORDER BY` | Byte-Reihenfolge | von der Collation abhängig | die Compose-Datenbank wird mit `--locale=C` angelegt |
| Zeilenform | Tupel | Tupel *(psycopgs Standard)* | explizit auf `tuple_row` festgelegt — jede Zeile wird hier positionell gelesen (`HSCode(*row)`), `dict_row` würde Spalten**namen** in die Felder entpacken und stillschweigend Unsinn erzeugen |

Unsortierte `SELECT`s haben auf keinem der beiden Backends eine garantierte Zeilenreihenfolge;
Gleichstände im Such-Ranking können dort also anders sortiert erscheinen. Dafür wurde kein
`ORDER BY` ergänzt — das würde das heutige SQLite-Verhalten ändern — und die Paritätstests prüfen
die Reihenfolge bei Gleichstand bewusst nicht.

**Das PostgreSQL-Schema wird aus dem einen SQLite-`SCHEMA`-String abgeleitet**, nicht als zweite
Kopie gepflegt; die beiden Backends können also nicht auseinanderlaufen. Die sieben
Entscheidungsmodule blieben unverändert, bis hin zu ihren `sqlite3.Connection`-Annotationen: Keines
führt SQL aus, sie reichen `conn` nur an `database.py` zurück — deshalb gibt der PostgreSQL-Zweig
den Wrapper per `cast` zurück.

### 🧩 SAP-GTS-Terminologieansicht — eine Simulation, keine Integration

> ⚠️ **Dies ist eine Terminologie- und Datenform-Simulation, keine SAP-Integration.**
> CustomsIQ ist mit keinem SAP-System verbunden und war es nie. Diese Schicht überführt
> die eigenen Ergebnisse von CustomsIQ in Strukturen, deren Feldnamen und Vokabular
> SAP GTS nachbilden — die dokumentierte `BAPIRET2`-Rückgabestruktur sowie die Bereichs-
> und Belegstatus-Terminologie von GTS — damit die Fachbegriffe auf einen Blick
> wiedererkennbar sind. **Die Ausgabe ist kein gültiger IDoc- oder BAPI-Beleg, und kein
> echtes SAP-System würde sie annehmen.** Eine echte Integration erforderte lizenziertes
> SAP GTS sowie eine SAP BTP ABAP Environment (oder ein On-Premise-SAP-System, erreichbar
> über RFC/OData) — nichts davon hat, nutzt oder behauptet dieses Projekt. Sie existiert,
> um Vertrautheit mit SAP-GTS-Konzepten zu zeigen, mehr nicht.

Derselbe Hinweis reist **in jeder Ausgabe mit** (`"SIMULATION": true` und ein
`DISCLAIMER`-Text im `HEADER`) und steht oben in der UI-Karte, damit die Ausgabe auch
dann beschriftet bleibt, wenn sie irgendwohin kopiert wird, wo diese README nicht ist.

**Was worauf abgebildet wird.** SAP GTS gliedert sich in drei Funktionsbereiche:
**Compliance Management** (SPL-Screening, Embargoprüfungen, Legal Control),
**Customs Management** (Zollanmeldungen, Einreihung, Abgabenermittlung) und
**Risk Management** (Preference Processing, Akkreditive, Ausfuhrerstattung).

| CustomsIQ | Bestehende Funktion | SAP-GTS-Entsprechung | Bereich |
|---|---|---|---|
| Sanktionslistenprüfung | `embargo_screener.screen_entity()` | **Sanctioned Party List (SPL) Screening** — gleicht Partnerdaten mit hochgeladenen Listeneinträgen ab und sperrt den Beleg bei einem Treffer | Compliance Mgmt |
| Prüfung / Prüfprotokoll | `review.submit_review()` | Die **Sperr-/Freigabeentscheidung und ihr Prüfprotokoll** — GTS sperrt einen Beleg, wenn eine Prüfung fehlschlägt, und er bleibt gesperrt, bis jemand ihn freigibt | Compliance Mgmt |
| Einreihung | `cn_classifier.classify()` | **Classification** — Ermittlung der Warennummer zu einem Produkt | Customs Mgmt |
| Zollberechnung | `tariff_calculator.calculate_duty()` | **Abgabenermittlung**; bei einem Präferenzsatz das *Ergebnis* von **Preference Processing** | Customs Mgmt / Risk Mgmt |
| Gesamtrisiko | `risk.assess_shipment()` | Kein einzelnes GTS-Objekt — das Ergebnis über alle drei Bereiche, weshalb es als bereichsübergreifender Beleg dargestellt wird |

Zwei Punkte, die genau benannt gehören, weil eine SAP-erfahrene Leserin sie prüft:

- **Preference Processing gehört zu GTS *Risk* Management, nicht zu Customs Management.**
  Die Abgabenermittlung liegt im Customs Management; die Ermittlung des Präferenzursprungs
  ist eine Risk-Management-Funktion. `calculate_duty` berührt beides, deshalb wird die
  erzeugte Meldung dem jeweils zutreffenden Bereich zugeordnet.
- **`review_decisions` ist nicht Legal Control.** Legal Control meint speziell die
  Ausfuhrgenehmigungs-Ermittlung für Dual-Use-Güter: GTS sperrt eine Position, wenn keine
  Lizenz zugeordnet werden kann, und nur deren Zuordnung hebt die Sperre auf. CustomsIQ hat
  **keine Lizenzstammdaten, keine Dual-Use-Einstufung und keine länderbezogene
  Embargoprüfung** — diese Zuordnung zu behaupten wäre also falsche Präzision. Was
  `review_decisions` tatsächlich abbildet, ist der Sperr-/Freigabeprozess samt Protokoll,
  der über *jeder* fehlgeschlagenen Compliance-Prüfung liegt.

**Die Ausgabeform.** `BAPIRET2` ist SAPs Standard-Rückgabestruktur und wird hier Feld für
Feld nachgebildet, einschließlich der echten Längen — Werte werden darauf gekürzt statt in
beliebiger Breite ausgegeben:

| Feld | Typ | Länge | Wofür |
|---|---|---|---|
| `TYPE` | CHAR | 1 | `S` Erfolg · `E` Fehler · `W` Warnung · `I` Info · `A` Abbruch |
| `ID` | CHAR | 20 | Nachrichtenklasse `ZCUSTOMSIQ_GTS`. Das `Z`-Präfix ist SAPs Kundennamensraum — die übliche Art zu sagen „kein Standard-SAP-Objekt" |
| `NUMBER` | NUMC | 3 | Feste Nummer je Ergebnis (`001` SPL-Treffer, `020` Präferenzsatz angewendet, …) |
| `MESSAGE` | CHAR | 220 | Der erzeugte Text |
| `LOG_NO` | CHAR | 20 | Die CustomsIQ-`subject_reference`, auf die echte Breite gekürzt |
| `LOG_MSG_NO` | NUMC | 6 | Laufende Nummer im Protokoll |
| `MESSAGE_V1`–`V4` | CHAR | 50 | Die eingesetzten Variablen, so wie SAP Meldungen zusammensetzt |
| `PARAMETER` | CHAR | 32 | Welcher GTS-Service die Meldung erzeugt hat |
| `ROW` | INT4 | — | Position in der RETURN-Tabelle |
| `FIELD` | CHAR | 30 | Der zugrunde liegende CustomsIQ-Faktor |
| `SYSTEM` | CHAR | 10 | `CUSTOMSIQ` — ein logischer Systemname, keine echte SAP-SID |

Echt sind: diese Feldnamen, Typen und Längen sowie die GTS-Bereichsnamen. CustomsIQs eigene
Konstruktion sind: die Nachrichtenklasse, die Nachrichtennummern, der Header-Umschlag und
das Statusvokabular `BLOCKED` / `PENDING` / `RELEASED` / `NOT_BLOCKED`.

**Beispiel** — dieselbe fixierte Bewertung, die der Risiko-Abschnitt und die CLI-Beispiele
schon verwenden (`assess_shipment(conn, "NO", "Northwind Maritime", 1000, description="cotton t-shirt")`
→ `0.6609`, hoch):

| ROW | TYPE | NUMBER | PARAMETER | MESSAGE |
|---|---|---|---|---|
| 1 | `E` | `001` | `SPL_SCREENING` | Sanctioned party list hit for 'Northwind Maritime' — real sanctions match: Northwind Maritime Holdings Ltd (1.00) |
| 2 | `I` | `010` | `CLASSIFICATION` | Commodity code 6109100000 determined — top match 6109100000 at 84.65% confidence |
| 3 | `S` | `020` | `PREFERENCE_DUTY` | Preferential duty rate applied — preferential rate 0.0% |
| 4 | `E` | `030` | `RISK_ASSESSMENT` | Composite risk HIGH (0.6609) — document blocked pending review |

`DOCUMENT_STATUS: "BLOCKED"`. Jede Zahl darin stammt aus der bestehenden Bewertung;
`sap_gts_bridge.py` rechnet nichts selbst — es nimmt fertig berechnete Ergebnisobjekte
entgegen, nie eine Datenbankverbindung, und ruft keine der Entscheidungsfunktionen auf.
Tests sichern genau das ab, über die Funktionssignaturen und den Quelltext.

### 📄 Rechnungsauslesung: was sie liest und was nicht

Laden Sie eine Handelsrechnung hoch, und die Einreihungs-, Zoll- und Risikoformulare
kommen vorausgefüllt zurück. Das ist eine **Komfortschicht, keine Entscheidungslogik**:
`document_extraction.py` macht aus einem PDF Zeichenketten und Zahlen, die
Entscheidungen bleiben, wo sie längst liegen. Das Modul importiert keines der sieben
Entscheidungsmodule — ein Test hält das fest — es kann also nicht stillschweigend zu
einem zweiten Klassifikator werden. Es ruft sie auch nicht selbst auf: der Endpunkt
liefert Felder, die Nutzerin prüft und korrigiert sie und drückt dann die Knöpfe, die
es schon gab. Dünne, kombinierbare Teile schlagen eine undurchsichtige Aktion, die
stellvertretend für ein Dokument entscheidet.

**Die eine Produktionsabhängigkeit, und warum sie zulässig war.** Dies ist die erste
Phase, die ein Paket in `requirements.txt` aufnimmt — die Datei, die Renders Build
installiert und die Phase 6 und 7 bewusst unangetastet ließen. Hier unvermeidlich, denn
das Feature *ist* PDF-Parsing; also wurde die Wahl vor der Festlegung überprüft statt
angenommen: `pypdf==6.19.0` liefert ein `py3-none-any`-Wheel (**es existiert überhaupt
kein plattformspezifisches Wheel**, es wird also nichts kompiliert), verlangt Python
≥3.9, was zur Untergrenze dieses Projekts passt, und hat genau eine Laufzeitabhängigkeit:
`typing_extensions`, über pydantic ohnehin vorhanden. Nicht nur auf PyPI geprüft,
sondern nach der Installation: im installierten Paket findet sich keine einzige `.so`,
`.pyd` oder `.dylib`. Kein Tesseract, kein poppler, keine Systembibliothek.

**Die Felder und wohin sie gehen.** Jedes Feld existiert, weil eine bestehende Funktion
es ohnehin als Argument nimmt:

| Feld | Erkannte Beschriftungen | Speist |
|---|---|---|
| `description` | Description of Goods · Goods Description · Description · Product · Commodity | `classify()` / `assess_shipment(description=)` |
| `hs_code` | HS Code · Commodity Code · Tariff Code · CN Code | `calculate_duty()` / `assess_shipment(hs_code=)` |
| `customs_value` | Invoice Value · Customs Value · Total Amount · Total | `calculate_duty()` / `assess_shipment()` |
| `currency` | aus der Betragszeile gelesen (EUR/USD/GBP, €/$/£) | nur zur Anzeige — dieses Projekt rechnet keine Währungen um, und so zu tun als ob hieße, eine Umrechnung zu erfinden |
| `country_of_origin` | Country of Origin · Origin · Made In | `calculate_duty()` / `assess_shipment()` |
| `party_name` | **Consignee** · Supplier · Exporter · Seller · Shipper | `assess_shipment()` → `screen_entity()` |

`party_name` bevorzugt **Consignee**, auch wenn eine Exporter-Zeile weiter oben steht,
denn die Sanktionsprüfung betrifft die Gegenpartei. Normalisiert wird nur dort, wo
dieses Projekt „gültig" bereits definiert: `validate_cn_code` für Codes,
`validate_country_code` für Ursprünge (`Norway` und `NO` ergeben beide `NO`).

**Die Felderkennung ist Regex auf beschrifteten Zeilen, und das ist eine bewusste
Obergrenze.** Ein Muster je Feld über eine Synonymliste, dazu kleine Normalisierer —
rund 60 Zeilen, keine Abhängigkeit. Die Alternative (LayoutLM, donut, spaCy) brächte
Modellgewichte und einen torch/transformers-Stack in ein Projekt, das
**scikit-learn für ein TF-IDF über 20 Zeilen abgelehnt hat**, und bräuchte immer noch
Training, um eine beschriftete Übereinstimmung auf strukturierten Dokumenten zu
schlagen. Unverklausuliert gesagt: **das funktioniert bei Rechnungen, die ihre Felder
zeilenweise beschriften.** Es liest *keinen* Wert aus einer rahmenlosen Tabellenspalte,
keinem zweispaltigen Layout, in dem Beschriftung und Wert im Textstrom weit
auseinanderfallen, keinem Fließtext und keinem nicht-englischen Dokument — die
Beschriftungen sind englisch, TR/DE-Beschriftungen sind ein bewusstes Nicht-Ziel dieser
Phase. Teilweise Auslesung ist der Normalfall; deshalb sind `missing` und
`completeness` Teil jeder Antwort und deshalb wird nie automatisch abgeschickt. Eine
echte Mehrdeutigkeit wird ausdrücklich behandelt: `1.234,56` und `12,450.00` werden
beide verstanden, indem das **zuletzt** auftretende Trennzeichen als Dezimalpunkt gilt.

Jedes Feld nennt die Beschriftung, auf die es passte, und die Zeile, aus der es stammt —
derselbe Erklärbarkeitsvertrag wie `matched_terms` bei `classify` und die
Faktoraufschlüsselung bei `risk`. Eine Prüferin sieht also, *warum* ein Wert gewählt
wurde, nicht nur welcher.

**Gescannte PDFs werden erkannt, nicht stillschweigend falsch behandelt.** Eine Seite
ohne Textebene kommt mit `has_text_layer: false` und einem entsprechenden Hinweis
zurück, statt mit einer leeren Feldliste, die wie ein Parser-Fehler aussieht. OCR ist
**nicht gebaut** — es ist ein dokumentierter Erweiterungspunkt: `pytesseract` braucht
die **Systembinärdatei** `tesseract-ocr`, und Renders nativer Python-Buildpack hat keine
apt-Schicht, um sie zu installieren. Dieselbe Überlegung hält Postgres und Docker vom
Live-Pfad fern; einen halbfertigen Haken einzubauen, den niemand nutzt, wäre schlechter,
als die Grenze beim Namen zu nennen.

**Upload-Sicherheit**, in der Reihenfolge der Ausführung:

| Maßnahme | Verhalten |
|---|---|
| Authentifizierung | Angemeldet, jede Rolle genügt (`document:extract` → `viewer`). Anonyme Aufrufe erhalten `401`, **bevor ein Byte gelesen wird**. Demo-Zugangsdaten sind auf Anfrage erhältlich, das Feature bleibt also für alle ausprobierbar |
| Größe | 2 MB, über den eingehenden Stream gezählt und mitten in der Übertragung abgebrochen → `413`. Bewusst nicht `Content-Length` — ein Header kann lügen, und erst zu puffern ist genau der Fehler, den man hier nicht haben will |
| Typ | Die Bytes müssen mit `%PDF-` beginnen → `415`. Dateiname und deklarierter `Content-Type` werden nie vertraut, der Dateiname landet in keinem Pfad |
| Struktur | Höchstens 10 Seiten; verschlüsselte PDFs werden abgelehnt; jeder Parse-Fehler wird ein sauberer `400`, nie ein Traceback |
| Rate | 10 Uploads pro Konto und Minute |
| Speicherung | **Es wird nichts gespeichert.** Die Bytes leben für einen Request in einem `BytesIO`. Kein `tempfile`, kein `open()`, kein Upload-Verzeichnis, keine Datenbankzeile, kein Dateiname und kein Dokumenttext im Log. Zwei Tests sichern das ab: ein Quell-Scan nach schreibenden Aufrufen und ein Schnappschuss von Arbeits- und Temp-Verzeichnis um einen echten Upload herum |

**Übertragen wird als roher Body, nicht als Multipart** — `Content-Type:
application/pdf` mit dem PDF als Request-Body. FastAPI braucht für Multipart-Uploads
`python-multipart`; der Fix für dessen aktuelle DoS-Meldung (CVE-2026-42561, unbegrenzte
Part-Header) kam in 0.0.27, und das verlangt Python ≥3.10 — über der 3.9-Untergrenze
dieses Projekts. Jede hier installierbare Version trägt also einen ungepatchten
Parser-DoS, ausgerechnet am einzigen Endpunkt, der beliebige Bytes annimmt. Multipart
wegzulassen nimmt diese ganze Fehlerklasse aus der Angriffsfläche und kostet nur das
Datei-Auswahlfeld in Swagger.

Das Rate Limit liegt **ausschließlich im Anwendungsspeicher** — ein Dict im
App-Prozess, nach Benutzername indiziert. Es fasst keine Datenbank an, die Backend-Wahl
aus Phase 6 ändert daran also nichts und kann es weder umgehen noch verdoppeln. Was das
effektive Limit ändert, ist nicht das Backend, sondern die Prozessanzahl: zwei Instanzen
gewähren je das volle Kontingent, und ein Neustart setzt den Zähler zurück. Für die eine
Instanz hier korrekt; gemeinsamer Zustand (Redis oder eine Tabelle) ist der Ausbauweg,
falls das einmal nicht mehr stimmt.

### 🔐 Authentifizierung ohne Abhängigkeit

`reviewer_name` war bisher das, was der Client hineingeschrieben hat. Fünf Stellen in
diesem Repo sagten das und versprachen diese Phase; jetzt ist es das angemeldete Konto —
und das Ganze kommt mit **null zusätzlichen Paketen**: `requirements.txt` ist unverändert,
der Build des Live-Deployments also Byte für Byte derselbe.

**Sitzungen statt JWTs.** Eine Sitzung ist ein undurchsichtiges
`secrets.token_urlsafe(32)` in einem `HttpOnly`-Cookie; gespeichert wird nur dessen
SHA-256, ein Datenbankleck liefert also keine nutzbare Sitzung. Schlichtes SHA-256 ist
*hier* richtig und sonst nirgends in diesem Modul: das Token besteht aus 256 Bit
CSPRNG-Ausgabe, und gegen ein nicht erratbares Geheimnis bringt eine langsame KDF
nichts. Der Grund, das einem JWT vorzuziehen, ist Widerrufbarkeit: Abmeldung und
Rollenwechsel greifen beim nächsten Request, während ein selbsttragendes Token bis zum
Ablauf gültig bleibt, sofern man keine Sperrliste anbaut — und eine Sperrliste ist genau
diese Sitzungstabelle mit Hut. Starlettes `SessionMiddleware` kam nicht infrage: sie
basiert auf signierten Cookies und braucht `itsdangerous` (geprüft: nicht installiert) —
eine neue Abhängigkeit für ein schwächeres Modell. CSRF deckt `SameSite=Lax` ab; `Secure`
wird aus `X-Forwarded-Proto` abgeleitet (Render terminiert TLS an einem Proxy), damit
`http://localhost` weiter funktioniert.

**Passwörter: `hashlib.pbkdf2_hmac` mit 600.000 Iterationen.** Dieselbe Prüfung wie bei
scikit-learn und openpyxl — und ungewöhnlicherweise durch eine Messung entschieden, nicht
durch Geschmack:

| Option | Urteil |
|---|---|
| `argon2-cffi` (argon2id) | Der beste Algorithmus, speicherhart, OWASPs erste Wahl. Abgelehnt: eine C-Extension-Abhängigkeit auf dem **Produktionspfad**, für Passwörter, die fiktive Daten schützen. |
| `bcrypt` / `passlib` | Ebenfalls C-Extension; passlib 1.7.4 (2020) ist faktisch unbetreut und bricht mit bcrypt 4.x, und bcrypt schneidet bei 72 Bytes stillschweigend ab. |
| `hashlib.scrypt` | Die speicherharte stdlib-Option und meine erste Wahl — **existiert aber auf dem Interpreter dieses Projekts nicht.** Gemessen: das venv-Python 3.9.6 ist gegen LibreSSL 2.8.3 gelinkt, `hasattr(hashlib, "scrypt")` ist `False`. In CI und Docker liefe es, auf dem Rechner der Entwicklerin nicht. Ausgeschieden wegen Portabilität, nicht wegen der Qualität. |
| **`hashlib.pbkdf2_hmac` ✅** | Immer vorhanden, null Abhängigkeiten, OWASPs empfohlene 600.000 Iterationen für SHA-256. Hier gemessen: 600k ≈ **160 ms**, 210k ≈ 57 ms. |

Der ehrliche Preis: **PBKDF2 ist nicht speicherhart**, ein Angreifer mit GPUs erzielt
dagegen also ein besseres Kostenverhältnis als gegen argon2id. Billig zu revidieren macht
das die Speicherform — `pbkdf2_sha256$600000$<Salt>$<Hash>` im Django-Stil: Algorithmus
und Arbeitsfaktor stehen in jeder Zeile und lassen sich bei der nächsten Anmeldung ohne
Migration anheben. Auch für einen unbekannten Benutzernamen läuft die KDF gegen einen
Dummy-Hash, damit sich Konten nicht über Zeitmessung aufzählen lassen; "falsches
Passwort" und "kein solcher Nutzer" liefern denselben Text.

`Settings.password_iterations` hält die Suite schnell (`tests/conftest.py` senkt den Wert,
so wie Django es für seine eigenen Testeinstellungen dokumentiert), während ein Test
festhält, dass der Produktionswert wirklich 600.000 ist, und einmal mit vollen Kosten hasht.

### 🛡️ Berechtigungsmatrix

Vier Rollen in der Ordnung `viewer < analyst < compliance_officer < admin`. Die Menge
verdient sich ihren Platz, weil eine Unterscheidung echt und nicht dekorativ ist:
**die Prüfung gegen Sanktionslisten ist die regulierte Freigabe** und braucht deshalb
einen Compliance-Officer, während Einreihung und Zoll Analystenarbeit sind — was sich
genau auf die drei bestehenden `subject_type`-Werte abbildet, statt neue Begriffe zu
erfinden.

Jeder rechnende Endpunkt bleibt **öffentlich**. Genau darum geht es in der Demo, und
nichts davon braucht eine Identität. Authentifizierung schützt Schreibzugriffe, den
Gesamtblick darauf, wer was geprüft hat, und die Kontenverwaltung.

| Endpunkt | anonym | viewer | analyst | Compliance-Officer | admin |
|---|:--:|:--:|:--:|:--:|:--:|
| `GET /search` · `/classify` · `/screen` · `/calculate-duty` · `/assess-risk` · `/codes/{code}/history` · `/codes/{code}/translations` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /dashboard/stats` — Kennzahlen | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /dashboard/stats` — `recent_reviews` (Namen + Notizen) | ❌ | ✅ | ✅ | ✅ | ✅ |
| `GET /review/history?subject_reference=…` (Spur eines Ergebnisses) | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /review/history` (vollständiges Prüfprotokoll) | ❌ 401 | ✅ | ✅ | ✅ | ✅ |
| `POST /review` — `classification`, `duty` | ❌ 401 | ❌ 403 | ✅ | ✅ | ✅ |
| `POST /review` — `screening` | ❌ 401 | ❌ 403 | ❌ 403 | ✅ | ✅ |
| `POST /extract-invoice` (Upload) | ❌ 401 | ✅ | ✅ | ✅ | ✅ |
| `POST /auth/register` · `/auth/login` · `/auth/logout` · `GET /auth/me` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `GET /auth/users` · `POST /auth/users/{username}/role` | ❌ 401 | ❌ 403 | ❌ 403 | ❌ 403 | ✅ |

`401` heißt "nicht angemeldet", `403` heißt "angemeldet, falsche Rolle" — ein Client muss
das auseinanderhalten können, um zwischen Login-Formular und Erklärung zu entscheiden,
deshalb sind die beiden nie austauschbar. Anonyme Aufrufe erhalten `/dashboard/stats` mit
`recent_reviews: []` und `recent_reviews_restricted: true`; die Kennzahlen bleiben
öffentlich. Die Berechtigungen stehen in genau einem Dict in `auth.py`, und eine
unbekannte Rolle oder Aktion verweigert immer — ein Tippfehler kann nichts gewähren.
`dashboard.py` ist daran unbeteiligt: die Schwärzung passiert im Endpunkt.

### 👤 Selbstregistrierung vergibt `analyst` — eine Demo-Entscheidung, kein Abbild echter Rollenvergabe

Wer sich registriert, erhält sofort die Rolle `analyst`, damit Besucherinnen eine
Einreihung freigeben *und* an einer Sanktionsfreigabe scheitern können, ohne dass jemand
ein Konto einrichtet. **So läuft RBAC-Onboarding in einem echten Zollcompliance-System
nicht ab, und das soll es hier auch nicht.** Dort werden Rollen *vergeben*, nicht gewählt:
eine Administratorin oder ein IdP-/HR-Gruppen-Mapping weist sie zu, nachdem die Person
verifiziert wurde; Selbstregistrierung gibt es entweder gar nicht, oder sie endet in einem
wartenden Zustand ohne Rechte. Einem Registrierungsformular die Macht zu geben,
Zolleinreihungen freizugeben, wäre in jedem echten Audit ein Befund.

Die produktionsnahe Variante ist eine Zeile: `auth.SELF_REGISTRATION_ROLE` auf `VIEWER`
setzen — neue Konten dürfen dann nur das Prüfprotokoll lesen, bis eine Administratorin sie
über `POST /auth/users/{username}/role` hochstuft, was es bereits gibt und bereits
admin-only ist. Dieselbe Begründung gilt dafür, dass die Demo-Konten überhaupt existieren:
für eine Portfolio-Demo auf fiktiven Daten angemessen, anderswo nicht vertretbar.

### 🕰️ Historische Freitext-Prüfer bleiben unangetastet

Zeilen, die vor der Einführung von Konten geschrieben wurden — und Zeilen, die die CLI
weiterhin schreibt — tragen einen Namen, für den niemand geradestehen kann. Sie bleiben
exakt so und werden gekennzeichnet: die API meldet `"authenticated": false`, die
Oberfläche zeigt neben dem Namen ein neutrales **Altbestand**-Label.

Drei Dinge passieren bewusst **nicht**:

- Kein Nachtragen, kein Raten, kein Löschen.
- Kein Abgleich über den Namen. `review_authorship` hängt an der **Zeilen-ID**; eine alte
  Zeile mit `alice` wird also *nicht* jemandem zugeordnet, der sich später als `alice`
  registriert — Identitätsübernahme per Registrierung ist konstruktiv ausgeschlossen, nicht
  per Richtlinie. Ein Test registriert genau den Altnamen und prüft, dass die Zeile nicht
  authentifiziert bleibt.
- Die CLI wird nicht als authentifiziert ausgegeben. Wer die CLI ausführen kann, kann
  ohnehin in die Datenbankdatei schreiben; eine Passwortabfrage dort wäre Theater. Ihre
  Zeilen sind wie alle anderen nicht authentifizierten gekennzeichnet.

### 🔗 Deterministische `subject_reference`

Jedes prüfbare Ergebnis trägt eine `subject_reference` — `sha256(f"{subject_type}:{normalisierte_eingabe}")`
— sodass dieselbe Anfrage zweimal gesendet immer denselben Gegenstand prüft; wiederholte
Einreichungen hängen sich an denselben gemeinsamen Prüfverlauf an, statt einen neuen zu eröffnen.
Das `subject_type`-Präfix verhindert, dass die drei Funktionen je auf demselben Hash kollidieren.

Die Normalisierung ist bei Textfeldern bewusst groß-/kleinschreibungsunabhängig (die Entscheidung
ändert sich dadurch nicht), bei Geldbeträgen dagegen exakt (ein anderer Zollwert **ist** eine
andere Entscheidung):

| Gegenstandstyp | Eingabe | `subject_reference` | Dieselbe Eingabe erneut? |
|---|---|---|---|
| classification | `"knitted cotton shirt"` | `ca8b1b95…fc3407` | Identisch |
| classification | `"KNITTED COTTON SHIRT"` | `ca8b1b95…fc3407` | **Wie oben** — Groß-/Kleinschreibung wird vor dem Hashen vereinheitlicht |
| screening | `"Northwind Maritime"` | `fa9ec5ed…b32c38c` | Identisch |
| duty | `hs_code=6109100000, country=DE, value=1000.00` | `8e4b03f6…602e3c2e` | Identisch |
| duty | `hs_code=6109100000, country=DE, value=1000.01` | `0a16c715…9c8f53` | **Unterschiedlich** — ein anderer Wert ist eine andere zu prüfende Entscheidung |

(Die vollständigen Hashes und dieselben Prüfungen stehen in `tests/test_review.py::TestDeterminism`.)

### 🧠 `/search` vs. `/classify` — ein Datenbestand, zwei Algorithmen

Beide ranken dieselbe `hs_codes`-Tabelle, beantworten aber verschiedene Fragen und scheitern
verschieden. `/search` ist ein **Nachschlagen**: schneller Zeichenabgleich, gut wenn man die
Formulierung ungefähr kennt. `/classify` ist eine **Vorschlagsmaschine**: sie gewichtet, wie
*selten* jedes Wort im Datenbestand ist, sodass ein kennzeichnender Begriff mehr zählt als ein
häufiger — und sie nennt, welche Ihrer Begriffe den Treffer bewirkt haben.

Am Beispieldatenbestand gemessen:

| Abfrage | `/search` (difflib) | `/classify` (TF-IDF) | |
|---|---|---|---|
| `knitted cotton shirt` | `6203420000` Herren**hosen** aus Baumwolle | `6109100000` **T-Shirts aus Baumwolle, gewirkt** | ✅ classify richtig |
| `lithium battery` | `8507600000` Lithium-Ionen-Akkus | dasselbe | unentschieden |
| `laptop` | `3926909700` Haushaltsartikel aus Kunststoff | `8471300000` Notebooks | ✅ classify richtig |

Zeile 1 ist der Fall, der dieses Modul rechtfertigt: `knitted` kommt in nur einer Beschreibung vor,
also lässt die Begriffsgewichtung es dominieren, während der Zeichenabgleich von der Masse der mit
"cotton trousers" geteilten Buchstaben in die Irre geführt wird. Zeile 3 zeigt den umgekehrten
Fehler: difflib liefert immer *irgendetwas*, `/classify` dagegen nichts, wenn kein Begriff geteilt
wird — statt Rauschen als Vorschlag auszugeben.

**Warum handgeschriebenes TF-IDF und nicht scikit-learn.** Implementiert ist sklearns eigene Formel
(geglättetes IDF `log((N+1)/(df+1))+1`, L2-normalisierte Vektoren, Kosinus über das Skalarprodukt)
in ~40 Zeilen Standardbibliothek-Arithmetik; `TfidfVectorizer` würde diese Daten also nahezu
identisch ranken — es gibt keine Genauigkeitslücke zu schließen. Dagegen zieht scikit-learn numpy
und scipy (~100 MB) ins Produktions-Image, um eine 20-zeilige Tabelle zu ranken. Und entscheidend:
**Erklärbarkeit würde mit sklearn mehr Code kosten, nicht weniger** — hier ist der Beitrag jedes
Begriffs `Abfragegewicht × Dokumentgewicht`, ohnehin auf dem Weg zum Score berechnet; mit sklearn
müsste man in `vectorizer.vocabulary_` greifen und in eine dünnbesetzte Matrix zurückindizieren.

Zu scikit-learn wechseln, sobald der Bestand ~10⁵ Zeilen übersteigt oder n-Gramme bzw. sublineare
Termfrequenz nötig werden. Der Index wurde früher bei jedem Aufruf neu aufgebaut — unproblematisch
bei 20 Mock-Codes, ~68 ms bei 10.000 — und sobald die echte EU-Kombinierte Nomenklatur mit 13.733
Codes eingebunden war (siehe
[🌍 Die echte EU-Kombinierte Nomenklatur 2026](#-die-echte-eu-kombinierte-nomenklatur-2026)), wurden
daraus ~150 ms pro Aufruf — also wurde das in diesem Hinweis bereits vorgesehene Caching
umgesetzt: ein Cache pro Verbindung, bei jedem Aufruf gegen die frisch gelesenen Zeilen auf
Korrektheit geprüft, keine neue Abhängigkeit.

**Ein gemessenes Detail:** KN-Beschreibungen stehen im Plural ("cables", "batteries"), Nutzer tippen
den Singular. Ohne Pluralfaltung erzielten `cable`, `biscuit`, `laptop` und `battery` jeweils **null
gegen jeden Code**. Der Tokenizer faltet daher `-ies → y`, das sibilantische `-es` und `-s`. Kein
Stemmer — nur die englische Pluralregel, die der Datenbestand verlangt.

**QA-Audit Bug #5: eine einzelne-Zeichen-Abfrage klassifizierte selbstbewusst, aber falsch.** Der
Tokenizer (`_WORD = re.compile(r"[a-z0-9]+")`) hat keine Mindestlänge für Token, und `_singular()`
faltet nur Wörter mit mehr als drei Zeichen — ein einzelnes Zeichen fließt also, wie auch immer es
entsteht, wie ein echtes Wort direkt in den TF-IDF-Index ein. Der echte 13.753-Code-EU-KN-Bestand
enthält 36 verschiedene einzelne Zeichen-Token (Ziffern `0`–`9`, Buchstaben `a`–`z`), meist
Fragmente, die ein Bindestrich oder Apostroph abtrennt ("T-shirts" → `t` + `shirts`; "Men's" →
`men` + `s`), oder Einheitensymbole in kurzen Beschreibungen ("175|g or more", "For a current
exceeding 16|A..."). Die IDF-Gewichtung dämpft ein häufiges Token wie `a` etwas, tut aber nichts
gegen die *Kürze des Dokuments selbst*: In `"175|g or more"` (insgesamt vier Token) beträgt das
normalisierte Gewicht von `g` allein `0,509` — der dominante Term im gesamten Vektor. Vor der
Behebung gemessen: `classify("g")` lieferte mit `0,5885` selbstbewusst einen unpassenden Treffer
gegen einen unzusammenhängenden DNA-Sequenz-Chemiecode, `classify("a")` mit `0,4959` gegen ein
unzusammenhängendes Ampere-Wert-Fragment — beide allein am Score nicht von einem echten Treffer zu
unterscheiden. Die Behebung fügt `classify()` eine einzige Prüfung hinzu: Erzeugt die Tokenisierung
einer Abfrage kein Token länger als ein Zeichen, liefert sie dasselbe ehrliche `[]`, das für
Null-Term-Überschneidungen bereits dokumentiert und getestet ist — bevor überhaupt bewertet wird.
Kein neuer Ausnahmetyp, denn das ist derselbe "nichts zu klassifizieren"-Fall, nur früher erkannt.
Entscheidend: Dies ist nur eine Schutzmaßnahme auf Abfrageseite — der Korpus-Index selbst bleibt
unangetastet, sodass eine echte Abfrage, die lediglich ein zufälliges einzelnes Zeichen-Fragment
*enthält* — wie `"cotton t-shirt"` selbst — weiterhin exakt wie zuvor klassifiziert wird
(`0,8464917087617252` gegen `6109100000`, bytegenau identisch).

### 🚫 Namensabgleich ist kein Produktabgleich

Die Sanktionsprüfung nutzt aus Konsistenzgründen denselben `difflib`-Kern ohne zusätzliche
Abhängigkeit, doch Namen brauchten zwei weitere Signale neben dem einfachen Verhältnis. Gemessen
an der Demoliste:

| Abfrage ↔ gelisteter Name | einfach | tokensortiert | Token-Überschneidung |
|---|---|---|---|
| `John Smith` ↔ `Smith, John` | 0,50 ❌ | **1,00** ✅ | 1,00 |
| `Northwind Maritime` ↔ `Northwind Maritime Holdings Ltd` | 0,73 ❌ | 0,73 ❌ | **1,00** ✅ |
| `Smith` ↔ `John Smith` | 0,67 | 0,67 | 1,00 ⚠️ |

Abweichende Wortstellung erfordert **Tokensortierung**, unvollständige Firmennamen eine
**Token-Überschneidung**: Bei einem Schwellenwert von 0,75 verfehlen die beiden anderen Signale
Zeile 2 vollständig. Der Überschneidungsterm zählt nur, wenn der kürzere Name mindestens zwei Token
hat — sonst würde ein einzelner häufiger Nachname (Zeile 3) auf jeden Datensatz passen, der ihn
enthält. Die Prüfung nimmt das Maximum der anwendbaren Signale und ist bewusst großzügig: Ein
falsch Negativer lässt eine sanktionierte Partei durch, ein falsch Positiver kostet eine Fachkraft
einen Blick.

**Das — und nicht die Produktsuche — wird `rapidfuzz` zuerst rechtfertigen.** Die beiden Signale
sind handgeschriebene Varianten von `token_sort_ratio` und `token_set_ratio`; hinzu kommen
`partial_ratio` und ein erheblich schnellerer Durchlauf. Die echte konsolidierte
EU-Finanzsanktionsliste umfasst Tausende Einträge, die bei jeder Prüfung erneut durchlaufen werden,
und erfordert eine Behandlung von Aliassen und Transliterationen, für die `difflib` keine Antwort hat.

### 🇪🇺 EU-Ausrichtung

> Datenmodell und Terminologie orientieren sich an der Kombinierten Nomenklatur der EU und an
> EU-Rahmenwerken für Außenhandels-Compliance — passend zum Zielmarkt (Compliance-Rollen im
> EU-Außenhandel).

Konkret bedeutet das:

| Bereich | Maßgebliche Quelle |
|---|---|
| Tarifcodes und Nomenklatur | [EU-TARIC-Datenbank](https://ec.europa.eu/taxation_customs/dds2/taric) — KN-8-Codes, TARIC-10 mit EU-Unterpositionen |
| Sanktions- und Embargoprüfung | Konsolidierte EU-Finanzsanktionsliste |
| Präferenzzollsätze | EU-Handelsabkommen |

---

## ⚙️ Einrichtung

```bash
# 1. Repository klonen
git clone https://github.com/Mutersec/CustomsIQ.git
cd CustomsIQ

# 2. Virtuelle Umgebung
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Abhängigkeiten
pip install -r requirements.txt

# 4. (Optional) Konfiguration
cp .env.example .env
```

### Konfiguration

Alle Einstellungen stammen aus Umgebungsvariablen oder aus `.env`:

| Variable | Standard | Beschreibung |
|---|---|---|
| `CUSTOMSIQ_DATABASE_PATH` | `customsiq.db` | Pfad zur SQLite-Datei (`:memory:` für eine flüchtige Datenbank) |
| `CUSTOMSIQ_DATABASE_URL` | *(nicht gesetzt)* | `postgresql://…`-URL. **Hat Vorrang vor `CUSTOMSIQ_DATABASE_PATH`, wenn gesetzt**; nicht gesetzt oder leer ⇒ SQLite wie bisher. Jedes andere Schema wird beim Start abgelehnt |
| `CUSTOMSIQ_LOG_LEVEL` | `INFO` | Python-Loglevel (`DEBUG`, `INFO`, `WARNING`, …) |
| `CUSTOMSIQ_SCREENING_THRESHOLD` | `0.75` | Mindest-Namensähnlichkeit (0–1) für einen Prüftreffer |
| `CUSTOMSIQ_PASSWORD_ITERATIONS` | `600000` | PBKDF2-HMAC-SHA256-Arbeitsfaktor (OWASP-Wert; ≈160 ms pro Hash) |
| `CUSTOMSIQ_SESSION_TTL_HOURS` | `12` | Gültigkeitsdauer des Session-Cookies |
| `CUSTOMSIQ_SEED_DEMO_USERS` | `true` | Legt die vier Demo-Konten in einer **leeren** users-Tabelle an. Für echte Deployments auf `false` setzen |
| `CUSTOMSIQ_UPLOAD_MAX_BYTES` | `2097152` | Größter akzeptierter Rechnungs-Upload (2 MB), beim Streamen des Bodys geprüft |
| `CUSTOMSIQ_UPLOAD_RATE_LIMIT_PER_MINUTE` | `10` | Erlaubte Uploads pro Konto und Minute |

### 📄 Eine Rechnung auslesen

Melden Sie sich an (jede Rolle genügt), wählen Sie im Bereich **Rechnungsauslesung** ein
PDF und klicken Sie **Felder auslesen**. Jedes Feld erscheint mit der Beschriftung, auf
die es passte, dazu eine Liste dessen, was nicht gefunden wurde. **Formulare
vorausfüllen** schreibt die Werte dann in die Einreihungs-, Zoll- und Risikofelder — und
hört dort auf. Es wird nichts für Sie abgeschickt: prüfen oder ändern Sie die Werte und
drücken Sie dann den Knopf, den Sie ohnehin kennen.

```bash
curl -c cookies.txt -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "<Benutzername>", "password": "<Passwort>"}'

curl -b cookies.txt -X POST "http://localhost:8000/extract-invoice" \
  -H "Content-Type: application/pdf" \
  --data-binary @rechnung.pdf
```

```json
{
  "fields": [
    {"name": "country_of_origin", "value": "NO", "label": "Country of Origin",
     "source_line": "Country of Origin:    Norway"},
    {"name": "customs_value", "value": "12450.0", "label": "Invoice Value",
     "source_line": "Invoice Value:        EUR 12,450.00"},
    {"name": "hs_code", "value": "6109100000", "label": "HS Code",
     "source_line": "HS Code:              6109100000"}
  ],
  "missing": [],
  "completeness": 1.0,
  "page_count": 1,
  "has_text_layer": true,
  "notes": []
}
```

Die Beispielrechnung dazu liegt als `tests/fixtures/sample_invoice.pdf` im Repo, und
`tests/fixtures/make_invoice_pdfs.py` erzeugt sie neu — das Fixture bleibt also keine
undurchsichtige Binärdatei.

### 🔐 Anmelden

Lesen und Rechnen braucht kein Konto. Eine Prüfung zu erfassen schon. Die Anmeldung hat
jetzt eine eigene Seite (`GET /login`) statt einer Karte in der Hauptanwendung — der Link
**Anmelden** im Kopfbereich führt dorthin, und eine erfolgreiche Anmeldung leitet zu `/`
zurück.

Beim ersten Start werden vier Demo-Konten angelegt — eines je Rolle, damit sich das
Berechtigungsmodell ausprobieren und nicht nur nachlesen lässt. Ihre Zugangsdaten werden
weder hier noch auf der Seite veröffentlicht, sondern **auf Anfrage** herausgegeben; die
Konten werden nur angelegt, wenn die `users`-Tabelle leer ist — ein Deployment mit echten
Konten kann sie also durch einen Neustart nicht untergeschoben bekommen — und
`CUSTOMSIQ_SEED_DEMO_USERS=false` schaltet sie ganz ab.

Eine Registrierung vergibt `analyst` — siehe [warum das eine Demo-Entscheidung ist](#-selbstregistrierung-vergibt-analyst--eine-demo-entscheidung-kein-abbild-echter-rollenvergabe).

```bash
# anmelden (oder registrieren) und das Cookie behalten
curl -c cookies.txt -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "<Benutzername>", "password": "<Passwort>"}'

# das Cookie ist es, was die Freigabe autorisiert
curl -b cookies.txt -X POST "http://localhost:8000/review" \
  -H "Content-Type: application/json" \
  -d '{"subject_type": "screening", "subject_reference": "<aus der /screen-Antwort>", "decision": "flagged"}'

curl -b cookies.txt "http://localhost:8000/auth/me"
curl -b cookies.txt -X POST "http://localhost:8000/auth/logout"
```

Im Browser ist das die Seite **/login**; nach der Anmeldung zeigt der Kopfbereich
Benutzernamen und Rolle, und die Prüf-Schaltflächen erscheinen genau an den Ergebnissen,
die Ihre Rolle freigeben darf. Alles ist übersetzt (EN/TR/DE) wie der Rest der Oberfläche.

### 🐳 Mit Docker ausführen

Nur für die lokale Entwicklung — **die [Live-Demo](https://customsiq-gs0u.onrender.com/) nutzt
weiterhin Renders bestehenden nativen Python-Deploy, unverändert davon.** Kein `render.yaml`,
kein Procfile; dieses Repo hat Render nie gesagt, wie es deployen soll, also ändert das
Hinzufügen eines `Dockerfile` hier daran nichts. Die Begründung siehe unten unter
[🐳 Docker für die lokale Entwicklung, nicht für Render (noch nicht)](#-docker-für-die-lokale-entwicklung-nicht-für-render-noch-nicht).
Trotzdem lohnenswert: Umgebungsparität für alle, die dieses Projekt prüfen oder ausführen wollen,
ohne von Hand ein Python-venv einzurichten, und es ist die Grundlage für den optionalen
PostgreSQL-Dienst — siehe [🐘 Mit PostgreSQL ausführen](#-mit-postgresql-ausführen) unten.

```bash
docker build -t customsiq .
docker run -p 8000:8000 customsiq
```

Oder für die lokale Entwicklung: `docker-compose.yml` verdrahtet dieselben drei Einstellungen
wie `.env.example` und fügt ein benanntes Volume hinzu, damit die eingesäte Datenbank Neustarts
übersteht:

```bash
docker compose up
```

Beide bedienen dieselbe App unter **http://localhost:8000/** wie ein direkt gestartetes
`uvicorn`. Mehrstufiger Build, `python:3.11-slim` (gepinnt auf die Version von CIs
`actions/setup-python`, nicht auf die zufällige lokale Version dieser Maschine) — das
Produktionsimage installiert nur die fünf Laufzeitpakete (`requirements-runtime.txt`), nie die
Entwicklungswerkzeuge (ruff/black/mypy/pytest) oder testexklusive Abhängigkeiten (`httpx`, nur
von `fastapi.testclient.TestClient` benötigt). Kein Hot-Reload eingerichtet — nach
Codeänderungen neu bauen, eine bewusste Vereinfachung für das, was "lokale Entwicklung" hier
brauchte, kein Versehen.

### 🐘 Mit PostgreSQL ausführen

**Optional, nur lokal. Die [Live-Demo](https://customsiq-gs0u.onrender.com/) bleibt bei SQLite** —
warum das eine bewusste Entscheidung und keine unfertige Migration ist, steht unter
[🐘 Zwei Backends: SQLite als Standard, PostgreSQL optional](#-zwei-backends-sqlite-als-standard-postgresql-optional).

`docker-compose.yml` enthält einen `postgres:16-alpine`-Dienst hinter einem **Profil**, sodass ein
einfaches `docker compose up` exakt das gewohnte SQLite-Setup bleibt. Zuschalten mit Profil *und*
URL:

```bash
CUSTOMSIQ_DATABASE_URL=postgresql://customsiq:customsiq@postgres:5432/customsiq \
  docker compose --profile postgres up
```

Außerhalb von Docker zuerst den optionalen Treiber installieren (er steht **nicht** in
`requirements.txt`):

```bash
pip install -r requirements-postgres.txt
CUSTOMSIQ_DATABASE_URL=postgresql://customsiq:customsiq@localhost:5432/customsiq \
  uvicorn src.customsiq.api:app
```

Das Schema wird beim ersten Verbinden angelegt, genau wie die SQLite-Datei. Für die
PostgreSQL-Paritätstests auf eine Datenbank zeigen, deren Name `test` enthält — die Fixture löscht
alle Tabellen und verweigert den Start andernfalls:

```bash
docker compose --profile postgres up -d postgres
docker exec customsiq-postgres-1 psql -U customsiq -d customsiq -c "CREATE DATABASE customsiq_test;"
CUSTOMSIQ_TEST_POSTGRES_URL=postgresql://customsiq:customsiq@localhost:5432/customsiq_test \
  pytest tests/test_postgres.py
```

Ohne diese Variable werden sie übersprungen — der normale `pytest`-Lauf bleibt schnell und ohne
zusätzliche Abhängigkeit.

---

## 🚀 Verwendung

### 💻 Interaktive CLI

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

Der CLI-Befehl `risk` unterstützt nur den HS-Code-Pfad (`risk <hs_code> <land> <wert>
<parteiname>`), keine Freitextbeschreibung — Grund siehe
[⚠️ Zusammengesetztes Risiko-Scoring](#️-zusammengesetztes-risiko-scoring). API und Weboberfläche
unterstützen auch eine Beschreibung.

### 🖥️ Weboberfläche

```bash
uvicorn src.customsiq.api:app --reload
```

Probieren Sie die **[Live-Demo](https://customsiq-gs0u.onrender.com/)**, oder öffnen Sie beim
lokalen Betrieb **http://localhost:8000/** für die Weboberfläche — beide Funktionen auf einer Seite.

### 🌐 REST-API

Derselbe Server stellt die JSON-API bereit:

Öffnen Sie anschließend **http://localhost:8000/docs** für die interaktive Swagger-Oberfläche.

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

### 🐍 Als Bibliothek

```python
from src.customsiq.database import get_connection, seed
from src.customsiq.search import search

conn = get_connection("customsiq.db")
seed(conn)

for result in search(conn, "lithium battery", limit=3):
    print(f"{result.hs_code.code}  {result.score:.0%}  {result.hs_code.description}")
```

---

## 🌐 API-Referenz

| Methode | Endpunkt | Beschreibung |
|---|---|---|
| `GET` | `/` | **Weboberfläche** (HTML-Seite) |
| `GET` | `/health` | Liveness-Prüfung — `{"service": "CustomsIQ API", "docs": "/docs", "status": "running"}` |
| `GET` | `/search` | Sortierte KN-Code-Treffer zu einer Produktbeschreibung |
| `GET` | `/classify` | Sortierte Code-Vorschläge mit Konfidenz und passenden Begriffen |
| `GET` | `/screen` | Sanktionslistentreffer zu einem Personen- oder Firmennamen |
| `GET` | `/calculate-duty` | Fälliger Zoll für eine Sendung, mit Begründung des Satzes |
| `POST` | `/review` | Speichert die Freigabeentscheidung zu einem früheren Klassifizierungs-, Prüf- oder Zollergebnis |
| `GET` | `/review/history` | Erfasste Prüfentscheidungen, neueste zuerst |
| `GET` | `/codes/{code}/history` | Versionszeitlinie eines KN-Codes (SCD Type 2), älteste zuerst |
| `GET` | `/codes/{code}/translations` | Deutsche/französische Beschreibung eines KN-Codes, neben der englischen |
| `GET` | `/dashboard/stats` | Aggregierte Statistiken: Referenzdaten, Prüfaktivität, KN-Importläufe |
| `GET` | `/assess-risk` | Zusammengesetzter Risiko-Score aus Einreihung, Prüfung und Zoll |
| `POST` | `/extract-invoice` | Liest ein hochgeladenes Rechnungs-PDF und gibt die gefundenen Felder zurück (Anmeldung erforderlich) |
| `GET` | `/sap-gts/compliance-check` | Dieselbe Risikobewertung in SAP-GTS-Terminologie (Simulation) |
| `GET` | `/sap-gts/legal-control/{subject_reference}` | Die Prüfentscheidungen eines Vorgangs als Sperr-/Freigabeprotokoll (Simulation) |
| `GET` | `/docs` | Interaktive Swagger-Oberfläche (automatisch erzeugt) |

**Typisierte Antworten.** Jede Route oben deklariert ein Pydantic-`response_model`, sodass `/docs`
und `/openapi.json` echte Feldschemas zeigen — einschließlich der BAPIRET2-Feldnamen der beiden
`/sap-gts/*`-Routen — statt eines untypisierten `additionalProperties: true`. Das ist eine reine
Typisierungsergänzung: jeder Antwortkörper ist unverändert, verifiziert durch einen Vergleich der
tatsächlichen JSON-Antwort jeder Route vor und nach Hinzufügen dieser Modelle.

**Sicherheits-Header.** Jede Antwort (Erfolge wie Fehler) trägt `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` und
`X-XSS-Protection: 0`, hinzugefügt durch eine kleine, global wirkende Middleware. Bewusst
**nicht** enthalten: eine Content-Security-Policy. Das Frontend ist eine einzelne Datei mit einem
großen inline `<script>`/`<style>`-Block; eine CSP, die streng genug wäre, um etwas zu bewirken,
bräuchte `'unsafe-inline'` sowohl für `script-src` als auch `style-src` — was den meisten Zweck
einer CSP zunichtemacht — oder eine Umstrukturierung des Frontends in externe Dateien, was echte,
eigenständige Arbeit jenseits von „aufwandsarmen Headern" ist. Eine CSP zu versenden, die reines
Sicherheitstheater wäre, wäre schlimmer, als die Lücke zu benennen.

**Parameter von `GET /search`**

| Parameter | Typ | Standard | Einschränkungen | Beschreibung |
|---|---|---|---|---|
| `q` | `str` | *erforderlich* | 1–500 Zeichen, nicht leer | Freitext-Produktbeschreibung |
| `limit` | `int` | `5` | 1–50 | Maximale Anzahl an Treffern |

**Parameter von `GET /classify`**

| Parameter | Typ | Standard | Einschränkungen | Beschreibung |
|---|---|---|---|---|
| `description` | `str` | *erforderlich* | 1–500 Zeichen, nicht leer | Freitextbeschreibung der Ware |
| `top_n` | `int` | `5` | 1–50 | Maximale Anzahl an Vorschlägen |

Der Zweitplatzierte liegt deutlich niedriger, weil er nur das *häufige* Wort `cotton` teilt, während
der Sieger auch das seltene `knitted` trifft — `matched_terms` macht das sichtbar statt implizit.

**Parameter von `GET /screen`**

| Parameter | Typ | Standard | Einschränkungen | Beschreibung |
|---|---|---|---|---|
| `name` | `str` | *erforderlich* | 1–500 Zeichen, nicht leer | Zu prüfender Personen- oder Firmenname |

Die Prüfung kennt kein `limit`: Jeder Treffer oberhalb des Schwellenwerts wird zurückgegeben — eine
still gekürzte Trefferliste wäre ein Compliance-Verstoß und nicht bloß ein schlechteres Ranking.

**Parameter von `GET /calculate-duty`**

| Parameter | Typ | Standard | Einschränkungen | Beschreibung |
|---|---|---|---|---|
| `hs_code` | `str` | *erforderlich* | KN-8 oder TARIC-10 | Code der eingeführten Ware |
| `country_of_origin` | `str` | *erforderlich* | ISO 3166-1 alpha-2 | Ursprung der Ware |
| `customs_value` | `float` | *erforderlich* | >= 0 | Angemeldeter Zollwert |

Qualifiziert der Ursprung für einen Präferenzsatz, gilt dieser; sonst der Regelsatz (MFN). Ein Code
**ohne** hinterlegten Satz liefert `404` statt null Zoll — eine Lücke im Datenbestand ist keine
zollfreie Einfuhr.

**`POST /review`-Body**

| Feld | Typ | Standard | Einschränkungen | Beschreibung |
|---|---|---|---|---|
| `subject_type` | `str` | *erforderlich* | `classification` \| `screening` \| `duty` | Art des geprüften Ergebnisses |
| `subject_reference` | `str` | *erforderlich* | nicht leer | Die `subject_reference` dieses Ergebnisses — nie neu eingegeben, immer der von der API gelieferte Wert |
| `decision` | `str` | *erforderlich* | `approved` \| `rejected` \| `flagged` | Das Urteil des Prüfers |
| `comment` | `str \| null` | `null` | — | Optionale Notiz |

Ein Feld `reviewer_name` gibt es nicht mehr: Prüfer ist, wer laut Session-Cookie
angemeldet ist. Es wurde **entfernt** statt entgegengenommen-und-ignoriert, damit kein
Client glauben kann, er habe den Namen in einer Prüfzeile gesetzt. Erfordert ein
angemeldetes Konto — `analyst` für `classification` und `duty`, `compliance_officer`
für `screening` (siehe [Berechtigungsmatrix](#️-berechtigungsmatrix)); anonyme Aufrufe
erhalten `401`, zu niedrig eingestufte `403`.

```bash
curl -X POST "http://localhost:8000/review" \
  -H "Content-Type: application/json" \
  -H "Cookie: customsiq_session=$TOKEN" \
  -d '{"subject_type": "duty", "subject_reference": "8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e", "decision": "approved", "comment": "confirmed correct"}'
```

```json
{
  "id": 1,
  "subject_type": "duty",
  "subject_reference": "8e4b03f6c0353ab018c024b6e7045251867255b083df5637f5d01ef5602e3c2e",
  "decision": "approved",
  "reviewer_name": "alice",
  "comment": "confirmed correct",
  "reviewed_at": "2026-01-01T12:00:00+00:00",
  "authenticated": true
}
```

**Parameter von `GET /review/history`**

| Parameter | Typ | Standard | Einschränkungen | Beschreibung |
|---|---|---|---|---|
| `subject_type` | `str \| null` | `null` | `classification` \| `screening` \| `duty` | Auf diesen Typ einschränken |
| `subject_reference` | `str \| null` | `null` | — | Auf diesen Gegenstand einschränken |
| `limit` | `int` | `50` | 1–200 | Maximale Anzahl zurückgegebener Entscheidungen |

```bash
curl "http://localhost:8000/review/history?subject_type=duty&limit=10"
```

**`GET /codes/{code}/history`** — außer dem Code selbst keine Parameter. `404` wenn der Code
unbekannt ist; ein Code, der existiert, aber nie von einem versionierten Import berührt wurde
(z. B. die eingesäten Demodaten), liefert `200 []`, keinen Fehler — dieselbe Konvention "leere
Liste, nie ein Fehler" wie bei `/search`.

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

**`GET /dashboard/stats`** — keine Parameter, keine zu validierende Eingabe. `review_by_decision`
und `review_by_subject_type` enthalten immer alle drei Schlüssel, standardmäßig auf `0`, sodass
eine frische Datenbank sauber gerendert wird, ohne den Aufrufer zu zwingen, sich gegen fehlende
Schlüssel abzusichern.

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

**`GET /assess-risk`** — genau eines von `description`/`hs_code` ist erforderlich (`400`, wenn
keines oder beide angegeben werden); `country_of_origin`, `party_name` und `customs_value` sind
immer erforderlich. Kombiniert `classify()`, `screen_entity()` und `calculate_duty()` — Gewichte
und Begründung siehe [⚠️ Zusammengesetztes Risiko-Scoring](#️-zusammengesetztes-risiko-scoring).
Dieses Beispiel ist ein echter Sanktionstreffer bei ansonsten sauberen Einreihungs-/Zolldaten —
die Prüfung allein (Gewicht 0,6) reicht aus, um "hoch" zu erreichen:

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

**Statuscodes**

| Code | Bedeutung |
|---|---|
| `200` | Erfolg — Liste der Treffer (kann leer sein) |
| `400` | `InvalidQueryError` — leere/zu lange Abfrage, fehlerhafter Code oder negativer Wert |
| `404` | `RateNotFoundError` — kein Zollsatz für diesen HS-Code hinterlegt, oder `HSCodeNotFoundError` bei `/codes/{code}/history` |
| `422` | Fehlender/ungültiger Parametertyp (FastAPI-Validierung) |

---

## 🧪 Qualität und Tests

Bei jedem Push und Pull Request läuft die vollständige Qualitätsprüfung über
[GitHub Actions](.github/workflows/ci.yml):

```mermaid
flowchart LR
    A["📥 Checkout"] --> B["🐍 Python 3.11"] --> C["📦 Installation"]
    C --> D["🔎 ruff"] --> E["🎨 black --check"] --> F["🏷️ mypy"] --> G["🧪 pytest ≥ 80 %"]
```

```bash
ruff check .                                                  # Linting
black .                                                       # Formatierung
mypy src                                                      # Typprüfung
pytest --cov --cov-report=term-missing --cov-fail-under=80    # Tests + Abdeckungsschwelle
```

### Aktuelle Testabdeckung

| Modul | Abdeckung |
|---|---|
| `api.py` · `config.py` · `database.py` · `embargo_screener.py` · `matching.py` | 🟢 100 % |
| `cn_classifier.py` · `exceptions.py` · `models.py` · `search.py` · `tariff_calculator.py` · `review.py` · `dashboard.py` · `risk.py` | 🟢 100 % |
| `scripts/import_cn_codes.py` | 🟢 91 % |
| `logging_config.py` | 🟢 100 % |
| `main.py` | 🟢 98 % |
| `pg_adapter.py` | 🟢 96 % |
| `auth.py` | 🟢 100 % |
| `document_extraction.py` | 🟢 99 % |
| **Gesamt** | **🟢 96,28 %** (420 Tests in ~5,7 s, Schwelle bei 80 %) — **kein Modul ist ausgenommen**. Der openpyxl-abhängige Excel-Lesepfad von `scripts/import_cn_codes.py` ist der Grund, warum die Gesamtzahl nicht höher liegt: openpyxl ist optional und in der CI nicht installiert, daher bleibt dieser Pfad dort ungetestet — dieselbe Behandlung, die das bereits vorhandene `_read_excel_rows` schon hatte. Die Suffix-Zusammenführungs- und Blattauswahl-*Logik*, die dieser Pfad aufruft, ist in reine Funktionen ausgelagert und vollständig getestet. |

Die 13 PostgreSQL-Paritätstests zählen dort *nicht* mit: Sie werden übersprungen, solange
`CUSTOMSIQ_TEST_POSTGRES_URL` nicht auf einen echten Server zeigt (die CI setzt die Variable; ein
einfaches lokales `pytest` braucht weder PostgreSQL noch den Treiber).

### Getestete Grenzfälle

| Fall | Erwartetes Verhalten |
|---|---|
| Leere Abfrage bzw. nur Leerzeichen oder leerer Name | `InvalidQueryError` → HTTP `400` |
| Abfrage länger als 500 Zeichen | `InvalidQueryError` → HTTP `400` |
| Eingabe in SQL-Injection-Form (`'; DROP TABLE hs_codes; --`) | Durch parametrisierte Abfragen sicher behandelt; Tabelle bleibt intakt |
| Emoji und Nicht-ASCII-Eingaben (`📱 Handy-Ladegerät`, `Ünal Çelik A.Ş.`) | Normal bewertet, kein Absturz |
| Umgekehrte Namensreihenfolge (`Aleksandr Voronin-Teske`) | Trifft den nachnamenzuerst gelisteten Eintrag |
| Unvollständiger Firmenname (`Northwind Maritime`) | Trifft den vollständig gelisteten Namen |
| Name ohne Entsprechung auf der Liste | Leeres Ergebnis, kein Fehler |
| Exakte Suche nach unbekanntem Code | `HSCodeNotFoundError` |
| Beschreibung ohne gemeinsamen Begriff | Leere Liste, nie ein Vorschlag mit Konfidenz null |
| Singular-Anfrage auf Plural-Beschreibung (`cable`, `battery`) | Wird gefaltet und trifft |
| Präferenzsatz für den Ursprung vorhanden | Setzt sich gegen den Regelsatz durch |
| Noch nicht in Kraft (`valid_from` in der Zukunft) | Wird ignoriert; es gilt der geltende Satz |
| HS-Code ohne hinterlegten Satz | `RateNotFoundError` → HTTP `404`, niemals null Zoll |
| Negativer Zollwert | `InvalidQueryError` → HTTP `400` |
| Zollwert null | Gültig — kein Zoll fällig |
| Erneutes Befüllen einer gefüllten Datenbank | Idempotent — keine doppelten Datensätze in allen Tabellen |
| Dieselbe Klassifizierungs-/Prüfanfrage, andere Groß-/Kleinschreibung | Gleiche `subject_reference` — vor dem Hashen vereinheitlicht |
| Gleiche Zolleingaben, anderer `customs_value` | Andere `subject_reference` — ein anderer Wert ist eine andere Entscheidung |
| Zwei Prüfentscheidungen zur selben `subject_reference` | Beide bleiben erhalten, neueste zuerst — Prüfdatensätze werden nie überschrieben |
| Unbekannter `subject_type` oder `decision` bei `POST /review` | `InvalidQueryError` → HTTP `400` |
| Erneuter Import eines Codes mit geänderter Beschreibung/Kategorie | Alte `hs_code_history`-Zeile geschlossen (`valid_to` gesetzt), neue geöffnet — nie gelöscht |
| Erneuter Import eines Codes mit identischen Daten | Keine neue `hs_code_history`-Zeile; `hs_codes` erhält einen harmlosen No-op-Upsert |
| `GET /codes/{code}/history` für einen eingesäten, nie versionierten Code | `200 []`, kein Fehler |
| `GET /codes/{code}/history` für einen unbekannten Code | `HSCodeNotFoundError` → HTTP `404` |
| `GET /dashboard/stats` bei einer frischen Datenbank (keine Prüfungen, keine Importe) | Alle Zählungen `0`, Aufschlüsselungsschlüssel vorhanden statt fehlend, leere Listen — nie `NaN%` im Frontend |
| Ein echter Sanktionstreffer, ansonsten saubere Einreihung/Zoll | Prüfung allein (`0,6 × 1,0`) erreicht "hoch" — die anderen Faktoren können es nicht verwässern |
| Beinahe-Treffer + niedrige Einreihungskonfidenz + fehlender Zollsatz zusammen | Landen bei "mittel" (`0,4989`), obwohl keiner allein bemerkenswert wäre |
| Beschreibung ohne gemeinsamen Begriff mit irgendeinem Code, in einer Risikobewertung | Einreihungsfaktor bewertet maximales Risiko (`1,0`); Zoll wird übersprungen, nicht mit "Satz nicht gefunden" verwechselt |
| Weder noch beide von `description`/`hs_code` bei `/assess-risk` angegeben | `InvalidQueryError` → HTTP `400` |
| Ein Präferenzsatz an oder über der Risiko-Obergrenze (synthetisch 90 % in Tests) | Zollfaktor begrenzt sich auf `1,0`, überschreitet nie den dokumentierten 0–1-Vertrag |

---

## 🌍 Die echte EU-Kombinierte Nomenklatur 2026

Jede frühere Phase betrieb die Such-/Einreihungs-Endpunkte gegen 20 erfundene Codes — genug, um
die Algorithmen zu zeigen, unbrauchbar, um ein echtes Produkt tatsächlich zu finden. Diese Phase
schließt diese Lücke **dauerhaft**, nicht mit einem Live-Importschritt: die offizielle
EU-Kombinierte Nomenklatur 2026 wird einmal verarbeitet, als Datei in dieses Repo committet
(`data/cn_nomenclature_2026.csv`, 3,1 MB) und bei jedem App-Start in `hs_codes` geladen —
einschließlich auf Render, dessen kostenlose Stufe das Dateisystem bei jedem Neustart zurücksetzt.
Kein Netzwerkzugriff, keine Abhängigkeit von irgendetwas, das zwischen Deployments überlebt —
derselbe „einmal verarbeiten, das Ergebnis committen"-Ansatz, den
`tests/fixtures/sample_invoice.pdf` für die Rechnungsauslesungs-Fixtures bereits nutzt.

**Echte, gemessene Zahlen, keine Schätzungen:**

| | |
|---|---|
| Quelle | EU-Kombinierte Nomenklatur 2026, offizieller Eurostat/DG-TAXUD-Export über [CIRCABC](https://circabc.europa.eu/), Englisch/Deutsch/Französisch |
| Eingebettete Blattcodes | **13.733** — jeder wirklich deklarierbare Code, CN-8 und TARIC-10 zusammen (Methodik unten) |
| Bundle-Größe | 3,1 MB CSV, im Repo committet |
| Zusätzlich bei jedem Kaltstart | **~90 ms** (CSV-Parsing + Upsert in `hs_codes` + Upsert in `hs_code_translations`, gemessen) |
| `classify()`-Kosten in dieser Größenordnung | ~150 ms kalt, **~20 ms** sobald der Cache pro Verbindung warm ist — siehe unten |
| `search()`-Kosten in dieser Größenordnung | ~440–490 ms pro Aufruf — für den Zeichen-Überlappungs-Algorithmus ist kein äquivalentes Caching möglich; eine bekannte, akzeptierte Kosten des größeren echten Katalogs, hier benannt statt unerklärt gelassen |

`cn_classifier.py` trug bereits einen Kommentar aus einer früheren Phase, der genau dieses Szenario
benannte: *„der Index wird bei jedem Aufruf neu aufgebaut — 0,1 ms bei 20 Codes, ~68 ms bei 10k.
Bei einem vollständigen KN-Import, der das spürbar macht, pro Verbindung cachen."* Dieser Import
tat das, also wurde die bereits vorgesehene Lösung umgesetzt: ein Cache pro Verbindung, der die
frisch gelesenen Zeilen mit dem zuletzt aufgebauten Index vergleicht und nur bei tatsächlicher
Abweichung neu berechnet — **kein** Zeilenzahl-Check, der ein In-place-Update mit gleichbleibender
Zeilenzahl übersehen und ein veraltetes Ergebnis liefern würde. Direkt verifiziert, nicht nur
begründet: nach dem Befüllen des Caches wurde ein In-place-Update vorgenommen, und der nächste
`classify()`-Aufruf baute korrekt neu auf, statt den alten Text zurückzugeben. Scores und Rangfolgen
sind unverändert gegenüber vorher — nur der überflüssige Neuaufbau entfällt. `search.py` hat keine
äquivalente Lösung: sein Zeichen-Überlappungsvergleich ist abfrageabhängig, nicht korpusabhängig,
es gibt also keinen Index zum Cachen, und seine ~450-ms-Kosten werden hier benannt statt still
gelassen.

**Wo sie liegen, und warum nicht als neue Spalten.** `hs_codes.description` bleibt Englisch,
unverändert; deutsche und französische Beschreibungen liegen in einer **neuen, separaten**
`hs_code_translations(code, language, description)`-Tabelle — genau dem Präzedenzfall folgend, den
[🕘 Versionierte KN-Codes](#-versionierte-kn-codes-scd-type-2) bereits für `hs_code_history`
gesetzt hat: `CREATE TABLE IF NOT EXISTS hs_codes (...)` kann niemals eine Spalte zu einer
bestehenden Datenbankdatei hinzufügen, eine neue Tabelle ist also der einzige Weg, der jede bereits
angelegte `customsiq.db` zuverlässig erreicht. Übersetzungen eines Codes gibt es unter
`GET /codes/{code}/translations`; ein Code ohne welche (jede der 20 Mock-Zeilen unten) liefert
`null` für `de`/`fr`, keinen Fehler.

**Was „Blattcode" tatsächlich bedeutet, gegen die echte Datei geklärt statt angenommen.** Der
Quellexport listet jede Hierarchieebene in einem Blatt, markiert durch eine `Hier. Pos.`-Spalte:
`8` für CN-8 (Kombinierte Nomenklatur) und `10` für TARIC-10 (die feineren EU-Zollanmeldecodes).
Ein CN-8-Code mit TARIC-10-Unterteilungen **ist für sich allein nicht wirklich deklarierbar** —
echte Anmeldungen erfordern den detailliertesten verfügbaren Code — er wird also zugunsten seiner
Kinder verworfen; ein CN-8-Code ohne weitere Unterteilung bleibt bestehen. Noch eine Falte, durch
direkte Prüfung verifiziert statt angenommen: das zweistellige Token hinter jedem Code
(„0101291000 80") ist ein Eurostat-*Statistik-Suffix*, nicht Teil des Warencodes selbst, und 1.098
Codes haben mehrere Suffix-Varianten mit tatsächlich unterschiedlichen Beschreibungen
(Gewichtsklassen, „zum Schlachten" vs. „andere"). Da `hs_codes.code` ein Primärschlüssel ist, muss
eine gewählt werden: Suffix `80` (der „keine Zusatzeinheit"-Standard, für jeden solchen Code
vorhanden) gewinnt; sonst die zuerst gesehene Variante. Ergebnis: **4.173 reine CN-8-Blätter +
9.560 TARIC-10-Codes = 13.733** — nicht die ~9.700, die ein naiver `Hier. Pos. == 8`-Filter ergeben
hätte.

**Das Bundle neu erzeugen** (eine künftige jährliche Aktualisierung, oder ein anderer Sprachsatz):

```bash
python scripts/import_cn_codes.py build-bundle \
  Nomenclature_EN.xlsx Nomenclature_DE.xlsx Nomenclature_FR.xlsx \
  --output data/cn_nomenclature_2026.csv
```

Das ist ein einmaliger/gelegentlicher Build-Schritt — die App führt ihn nie aus; sie liest nur die
committete CSV. Der ursprüngliche einsprachige `import`-Befehl von `scripts/import_cn_codes.py`
(unten) ist unverändert und funktioniert weiterhin für eine routinemäßige jährliche Auffrischung,
sobald ein Bundle bereits existiert.

Der 20-zeilige Mock-Katalog unten bleibt **unverändert neben den echten Daten erhalten** — er wird
nicht ersetzt. Der Standard von `seed()` bleibt derselbe wie immer, dieselben 20 Codes (jede
Test-Fixture in diesem Repo hängt davon ab und läuft vollständig unverändert weiter); das echte
13.733-Code-Bundle wird nur in der Live-App obendrauf geladen. Keiner der Mock-Codes kollidiert mit
echten — verifiziert, nicht angenommen: `8517120000`, `6109100000` und die übrigen wurden für
frühere Phasen erfunden und entsprechen keinen echten CN-8-Einträgen von 2026. Ein kleiner, ehrlich
zu benennender Nebeneffekt: die Kategorie-Bezeichnungen der Mock-Daten stammen von vor
`import_cn_codes.py`s kapitelbasierter Zuordnung und widersprechen ihr an zwei Stellen — Kapitel 64
(Schuhe) ist im Mock-Set `"Textilien"`, im echten `"Schuhe"`; Kapitel 09 (Kaffee) ist im Mock-Set
`"Lebensmittel"`, im echten `"Pflanzliche Erzeugnisse"`. Beide Bezeichnungen erscheinen im
Live-Katalog für ihre jeweiligen Kapitel, unabgeglichen — die Mock-Zeilen werden außerdem namentlich
in mehreren fixierten Tests verwendet, ihre „Korrektur" lag also außerhalb des Umfangs dieser Phase.

Die Datenbank wird mit **20 repräsentativen KN-/TARIC-Codes aus 8 Kategorien** vorbefüllt, formuliert
im Stil der EU-Kombinierten Nomenklatur — dem ursprünglichen Mock-Set, oben beschrieben:

| Kategorie | Codes |
|---|---|
| 📱 Elektronik | 5 |
| 👕 Textilien | 5 |
| 🍫 Lebensmittel | 5 |
| 💊 Pharmazeutika · 🚗 Kfz · 🪑 Möbel · 🧴 Kunststoffe · 🔩 Metalle | je 1 |

<details>
<summary><b>Alle 20 hinterlegten Codes anzeigen</b></summary>

| KN-/TARIC-Code | Beschreibung | Kategorie |
|---|---|---|
| `8517120000` | Mobiltelefone und Smartphones | Elektronik |
| `8471300000` | Tragbare automatische Datenverarbeitungsmaschinen (Notebooks) | Elektronik |
| `8528721000` | Farbfernsehempfangsgeräte | Elektronik |
| `8544421000` | USB-Kabel und Datenkabel | Elektronik |
| `8507600000` | Lithium-Ionen-Akkumulatoren | Elektronik |
| `6109100000` | T-Shirts aus Baumwolle, gewirkt | Textilien |
| `6203420000` | Herrenhosen aus Baumwolle | Textilien |
| `6204620000` | Damenhosen aus Baumwolle | Textilien |
| `6110200000` | Pullover und Sweatshirts aus Baumwolle | Textilien |
| `6402990000` | Schuhe mit Laufsohlen aus Kautschuk oder Kunststoff | Textilien |
| `0901210000` | Gerösteter Kaffee, nicht entkoffeiniert | Lebensmittel |
| `1806320000` | Schokoladentafeln, ohne Füllung | Lebensmittel |
| `2009110000` | Gefrorener Orangensaft | Lebensmittel |
| `0406100000` | Frischkäse | Lebensmittel |
| `1905310000` | Süße Kekse | Lebensmittel |
| `3004900000` | Arzneiwaren zu therapeutischen Zwecken | Pharmazeutika |
| `4011100000` | Neue Luftreifen für Personenkraftwagen | Kfz |
| `9403300000` | Büromöbel aus Holz | Möbel |
| `3926909700` | Haushaltsartikel aus Kunststoff | Kunststoffe |
| `7326909800` | Verschiedene Waren aus Eisen oder Stahl | Metalle |

</details>

> ⚠️ Hierbei handelt es sich um **Demodaten** für Entwicklung und Tests. Für den Produktivbetrieb
> wird die offizielle Nomenklatur aus der
> [EU-TARIC-Datenbank](https://ec.europa.eu/taxation_customs/dds2/taric) benötigt.

### Sanktionsliste

Die Tabelle `sanctioned_entities` wird mit **18 Einträgen** im Stil der konsolidierten
EU-Finanzsanktionsliste vorbefüllt: erfundene Handels-, Schifffahrts- und Ingenieurunternehmen sowie
einige synthetische Personennamen, nachnamenzuerst gespeichert, wie es echte Listen veröffentlichen.

| Feld | Beispiel |
|---|---|
| `name` | `Northwind Maritime Holdings Ltd` · `Voronin-Teske, Aleksandr` |
| `country` | `CY`, `AE`, `DE`, `RS`, `MT`, `NL`, … |
| `list_source` | `EU Consolidated Financial Sanctions List` · `EU Dual-Use Export Control Watchlist` |
| `date_added` | `2023-04-12` |

> 🚨 **Jeder Name in dieser Liste ist fiktiv.** Keiner entspricht einer real sanktionierten Person
> oder Organisation, und die Liste darf niemals für eine echte Prüfung verwendet werden. Der
> Produktivbetrieb erfordert die offizielle konsolidierte EU-Finanzsanktionsliste.

### Zollsätze

Die Tabelle `tariff_rates` wird mit **18 Zeilen** vorbefüllt: Regelsätze (MFN) für Codes aus dem
Beispiel oben sowie Präferenzsätze aus zwei Handelsabkommen — darunter eine 0-%-Präferenz und ein
zukünftig datierter Satz, den der `valid_from`-Filter korrekt ignoriert.

| Feld | Beispiel |
|---|---|
| `hs_code` | `6109100000` |
| `country_of_origin` | `NO`, `CH`, `JP`, `KR` — oder `ALL` für den Regelsatz |
| `rate_type` | `standard` · `preferential` |
| `rate_percent` | `12.0` · `0.0` |
| `trade_agreement` | `EU-Solvia Free Trade Agreement` · `EU-Meridian Economic Partnership` · `null` |

> 🚨 **Die Sätze und beide Handelsabkommen sind fiktiv.** Echte Zollsätze und Präferenzursprünge
> stammen aus der EU-TARIC-Datenbank; verwenden Sie diese Zahlen niemals für eine echte Anmeldung.

### Eine KN-Nomenklatur-Aktualisierung importieren

Die Live-Demo läuft bereits mit der echten EU-Kombinierten Nomenklatur 2026 mit 13.733 Codes (siehe
[🌍 Die echte EU-Kombinierte Nomenklatur 2026](#-die-echte-eu-kombinierte-nomenklatur-2026) oben) —
dieser Abschnitt dient dazu, sie aufzufrischen oder lokal einen anderen einsprachigen KN-Export zu
importieren:

**1. Datei beschaffen** (manuell — der Importer geht nie ins Netz):

| Quelle | Was zu nehmen ist |
|---|---|
| [Eurostat RAMON](https://ec.europa.eu/eurostat/ramon/) → *Nomenclatures* → *CN* | Die KN des laufenden Jahres als CSV oder Excel |
| [TARIC-Auskunft](https://ec.europa.eu/taxation_customs/dds2/taric/) | Ein Warennummern-Export mit englischen Beschreibungen |

**2. Importieren:**

```bash
python scripts/import_cn_codes.py path/to/cn_codes.csv
```

| Option | Standard | Zweck |
|---|---|---|
| `--db` | `CUSTOMSIQ_DATABASE_PATH` | Zieldatenbank; in eine eigene Datei importieren, um die Mock-DB zu erhalten |
| `--code-column` | automatisch erkannt | Falls der Export eine unbekannte Spaltenüberschrift nutzt |
| `--description-column` | automatisch erkannt | Dasselbe für die Beschreibungsspalte |
| `--batch-size` | `1000` | Zeilen pro Upsert |
| `--version-label` | ein Zeitstempel | Label für diesen Lauf (z. B. `CN2026`), bei jedem geänderten Code erfasst |

Der Importer erkennt die üblichen RAMON-/TARIC-Spaltennamen automatisch, leitet die Kategorie aus
dem HS-Kapitel (den ersten beiden Ziffern) ab, überspringt die Kapitel- und Positionszeilen oberhalb
der achtstelligen Endcodes, protokolliert fehlerhafte Zeilen und überspringt sie statt abzubrechen,
und **führt einen Upsert von `hs_codes` auf den Code aus — ein erneuter Lauf aktualisiert die
aktuellen Daten, statt sie zu verdoppeln, genau wie bisher**. Neu: Ein Code, dessen Beschreibung
oder Kategorie sich tatsächlich geändert hat, erhält zusätzlich einen geschlossenen und neu
geöffneten Eintrag in `hs_code_history` (siehe [🕘 Versionierte KN-Codes](#-versionierte-kn-codes-scd-type-2)
oben), sodass ein erneuter Import den früheren Wortlaut eines Codes nie stillschweigend verliert.
Mit `GET /codes/{code}/history` lässt sich die vollständige Zeitlinie eines Codes abrufen — das ist
auch der sichtbare Beweis der Versionierung in dieser Demo.

Die Anwendung auf die importierte Datenbank zeigen lassen:

```bash
CUSTOMSIQ_DATABASE_PATH=cn_full.db uvicorn src.customsiq.api:app
```

Excel-Eingabe benötigt zusätzlich `pip install openpyxl`; das ist bewusst keine Projektabhängigkeit,
da nur dieses Werkzeug sie je bräuchte. Ein CSV-Export erübrigt sie vollständig.

> 📜 **Quellenangabe.** Die Kombinierte Nomenklatur ist öffentliche Referenzdatenbasis der
> Europäischen Union (© Europäische Union) und — einschließlich der Weiterverbreitung
> abgeleiteter Auszüge, mit Quellenangabe — gemäß der
> [Weiterverwendungspolitik der Kommission](https://ec.europa.eu/info/legal-notice_en) nachnutzbar.
> `data/cn_nomenclature_2026.csv` **ist genau ein solcher Auszug**: 13.733 Blattcodes mit
> englischer, deutscher und französischer Beschreibung, abgeleitet aus dem offiziellen
> Eurostat/DG-TAXUD-CIRCABC-Export und im Rahmen dieser Politik ins Repo committet — ein
> Unterschied zu früheren Phasen, die nur auf offizielle Quellen verwiesen, ohne Daten
> einzubetten. Die Sanktionsliste und die Zollsätze auf dieser Seite bleiben vollständig
> fiktiv und sind davon unberührt.

---

## 🗺️ Roadmap

**Alle acht Funktionen sind einsatzbereit — es bleibt kein Gerüst übrig**, und jedes Modul wird
von der Abdeckungsschwelle gemessen:

| Modul | Status | Funktionsumfang |
|---|---|---|
| `search.py` | ✅ **Ausgeliefert** | Unscharfe KN-Code-Suche über CLI und REST |
| `cn_classifier.py` | ✅ **Ausgeliefert** | TF-IDF-Einreihung mit Konfidenz und passenden Begriffen |
| `embargo_screener.py` | ✅ **Ausgeliefert** | Namensprüfung gegen Verbotslisten über CLI und REST |
| `tariff_calculator.py` | ✅ **Ausgeliefert** | Zollberechnung mit Auswahl des Präferenzsatzes |
| `review.py` | ✅ **Ausgeliefert** | Vier-Augen-Prüfprotokoll für alle drei Entscheidungen |
| KN-Code-Versionierung (SCD Type 2) | ✅ **Ausgeliefert** | `hs_code_history` + `cn_code_versions`, bereitgestellt über `GET /codes/{code}/history` |
| `dashboard.py` | ✅ **Ausgeliefert** | Schreibgeschützte Berichtsschicht über Phase 1 & 2, via `GET /dashboard/stats` |
| `risk.py` | ✅ **Ausgeliefert** | Zusammengesetzter Sendungs-Risiko-Score über Einreihung, Prüfung und Zoll, via `GET /assess-risk` |
| `auth.py` (RBAC) | ✅ **Ausgeliefert** | Konten, Sitzungen und vier Rollen; `reviewer_name` kommt jetzt aus der Sitzung |
| `document_extraction.py` | ✅ **Ausgeliefert** | Rechnungs-PDF-Upload, der die Einreihungs-, Zoll- und Risikoformulare vorausfüllt |
| `sap_gts_bridge.py` | ✅ **Ausgeliefert** | SAP-GTS-Terminologieansicht über bestehende Ergebnisse — gekennzeichnete Simulation, keine Integration |
| Echte EU-Kombinierte Nomenklatur 2026 | ✅ **Ausgeliefert** | 13.733 echte, dreisprachige Blattcodes, bei jedem Start neben den ursprünglichen Mock-Daten geladen |

Geplante Erweiterungen: länderbezogene Embargokontrollen und Waren-/Bestimmungsbeschränkungen,
Alias- und Transliterationsbehandlung für Entitätsnamen, Kontingent- und Antidumping-Komponenten
auf der Zollberechnung, das Zwischenspeichern des Klassifikator-Index, sobald ein vollständiger
KN-Import den Neuaufbau pro Aufruf spürbar macht, **Single Sign-on über einen externen
Identity Provider** (SSO/SCIM) anstelle des lokalen Passwortspeichers, nachdem
[RBAC ausgeliefert ist](#-authentifizierung-ohne-abhängigkeit), kontobezogene Sperren oder
Rate Limits nach wiederholt fehlgeschlagenen Anmeldungen (heute bremst nur die 160-ms-KDF),
ein CLI-Befehl `history <code>`, der den
API-Endpunkt spiegelt, ein eigener, paginierter `GET /cn-imports`-Endpunkt zum vollständigen
Durchsuchen des `cn_code_versions`-Protokolls (`/dashboard/stats` stellt die zuvor nicht
exponierten `fetch_cn_import_runs`-Daten jetzt bereit, aber nur die jüngsten — für die vollständige
Liste bleibt ein dedizierter, filterbarer Endpunkt offen), ein CLI-`risk`-Pfad, der eine
Freitextbeschreibung akzeptiert (heute nur auf den HS-Code-Pfad beschränkt — siehe
[⚠️ Zusammengesetztes Risiko-Scoring](#️-zusammengesetztes-risiko-scoring)), sowie
persistierte/prüfbare Risikobewertungen, falls ein echter Einsatz jemals den Score selbst und
nicht nur die drei zusammengefassten Entscheidungen prüfen muss. Die Live-Deployment auf
PostgreSQL umzustellen steht bewusst *nicht* auf dieser Liste — das Backend funktioniert bereits
(siehe [🐘 Zwei Backends](#-zwei-backends-sqlite-als-standard-postgresql-optional)); es fehlt nur
eine Datenbank, die im kostenlosen Tarif nicht nach 30 Tagen ausläuft.

---

## 📁 Projektstruktur

```text
CustomsIQ/
├── .github/workflows/ci.yml     # ruff → black → mypy → pytest
├── Dockerfile                   # Image für die lokale Entwicklung — siehe 🐳 Mit Docker ausführen
├── docker-compose.yml           # app + optionaler Postgres-Dienst (--profile postgres)
├── .dockerignore
├── requirements-runtime.txt     # Laufzeit-Teilmenge von requirements.txt, vom Dockerfile genutzt
├── requirements-postgres.txt    # optionaler psycopg-Treiber — bewusst NICHT in requirements.txt
├── src/
│   ├── customsiq/
│   │   ├── models.py            # HSCode- + SanctionedEntity- + TariffRate- + ReviewDecision- + HSCodeVersion- + ImportRun-Datensätze
│   │   ├── database.py          # SQLite-/Postgres-Schicht + Beispieldaten + SCD-Type-2-Versionierung
│   │   ├── pg_adapter.py        # PostgreSQL-Dialektadapter — nur bei gesetzter URL importiert
│   │   ├── matching.py          # gemeinsame Validierung + Ähnlichkeitsbewertung
│   │   ├── search.py            # KN-Code-Ranking
│   │   ├── cn_classifier.py     # TF-IDF-Einreihung + Begründung
│   │   ├── embargo_screener.py  # Namensprüfung gegen Sanktionslisten
│   │   ├── tariff_calculator.py # Zollsatzwahl + Berechnung
│   │   ├── review.py            # Prüfprotokoll (Vier-Augen-Prinzip)
│   │   ├── auth.py              # Konten, Sitzungen, Rollen — nur stdlib, keine neue Abhängigkeit
│   │   ├── document_extraction.py # Rechnungs-PDF → Felder (pypdf + Regex auf beschriftete Zeilen)
│   │   ├── sap_gts_bridge.py     # stellt Ergebnisse in SAP-GTS-Begriffen dar — Simulation, keine Integration
│   │   ├── dashboard.py         # schreibgeschützte Aggregation über Phase 1 & 2
│   │   ├── risk.py              # zusammengesetzter Sendungs-Risiko-Score
│   │   ├── exceptions.py        # typisierte Fehlerhierarchie
│   │   ├── config.py            # pydantic-settings / .env
│   │   ├── logging_config.py    # gemeinsames Logging-Setup
│   │   ├── main.py              # CLI-Einstiegspunkt
│   │   ├── api.py               # FastAPI-Anwendung (liefert auch das Frontend)
│   │   └── static/index.html    # Weboberfläche — eine Datei, kein Build-Schritt
│   └── utils/validators.py      # Validierung von KN-/TARIC-Format und Ländercode
├── data/cn_nomenclature_2026.csv # eingebettete EU-Kombinierte Nomenklatur 2026 — 13.733 Blattcodes, EN/DE/FR
├── scripts/import_cn_codes.py   # offizielle KN-Datei → hs_codes, versioniert Änderungen (SCD Type 2);
│                                #   erzeugt auch das obige data/-Bundle (Subcommand build-bundle)
├── tests/                       # 358 Tests — Unit, API, CLI, Einreihung, Prüfung, Zoll, Review, Import, Dashboard, Risiko, Auth/RBAC, Auslesung
│   └── fixtures/                #   CN-Beispieldatei + Rechnungs-PDFs (make_invoice_pdfs.py erzeugt sie neu)
│   ├── conftest.py              #   senkt den Passwort-Arbeitsfaktor für die Suite
│   ├── helpers.py               #   angemeldete TestClient-Helfer
│                                #   + 13 Postgres-Paritätstests, ohne konfigurierten Server übersprungen
│   └── fixtures/                # Beispiel-KN-Export für die Importer-Tests
├── pyproject.toml               # ruff · black · mypy · pytest · coverage
├── requirements.txt
└── .env.example
```

---

## 📄 Lizenz

Veröffentlicht unter der **MIT-Lizenz**.

<div align="center">

[🇬🇧 English](README.md) · [🇹🇷 Türkçe](README.tr.md) · **🇩🇪 Deutsch**

</div>
