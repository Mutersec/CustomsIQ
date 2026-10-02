"""What the assistant says: reply templates and the help-desk answers, in EN/TR/DE.

Kept apart from the parsing logic in `assistant.py` so the wording can be edited
without touching code; prose lines here are exempt from the line-length rule.
"""

TEXT: dict[str, dict[str, str]] = {
    "en": {
        "ask_product": 'Which goods are they? Name the product (e.g. "apples") or give its CN code.',
        "ask_origin": "Which country are the goods coming from?",
        "ask_quantity": 'How much is it? For example "10 t", "500 kg" or "200 pieces".',
        "ask_price": 'What is the price? For example "1000 EUR per tonne" or "10,000 EUR in total".',
        "unknown_product": (
            'I could not match "{product}" to a tariff code. Try the English name, '
            'or give the CN code directly (e.g. "code 0808.10").'
        ),
        "unit_mismatch": (
            "The price is per {price_unit} but the quantity is in {unit}. "
            "Please give both in the same unit."
        ),
        "intro": "Here is the estimate for {product} from {origin}:",
        "intra_eu": (
            "{origin} is an EU member state, so goods moving from there into the EU pay "
            "no customs duty (intra-EU trade)."
        ),
        "non_eu_destination": (
            "Note: this calculator uses the EU tariff. Import duties for {destination} are "
            "not in this system."
        ),
        "no_rate": (
            "No duty rate is on record for {code} in this system, so I can't give the duty. "
            "The goods value is shown above; check the rate in the EU TARIC database."
        ),
        "assumed_total": (
            "I took {amount} as the total price. If it is per unit, write e.g. "
            '"1000 EUR per tonne".'
        ),
        "currency_note": (
            "EU duty is assessed in EUR; amounts are shown in {currency} and the official "
            "customs exchange rate may differ."
        ),
        "disclaimer": (
            "Estimate only: import VAT, freight, insurance and other charges are not included."
        ),
        "classify_intro": 'The closest codes for "{product}":',
        "screen_none": 'No sanctions-list match for "{name}".',
        "screen_hits": 'Possible sanctions-list matches for "{name}":',
        "screen_ask": "Which person or company should I screen? Write the name.",
        "help": (
            "I can estimate customs duty, find a CN code and screen a name. Try: "
            '"10 t of apples from Turkey, 1000 EUR per tonne".'
        ),
        "goods_value": "Goods value",
        "duty": "Customs duty",
        "total": "Total",
        "rate": "Rate",
    },
    "tr": {
        "ask_product": 'Hangi ürün? Ürün adını (ör. "elma") ya da GTİP kodunu yazın.',
        "ask_origin": "Mal hangi ülkeden geliyor?",
        "ask_quantity": 'Miktar ne kadar? Ör. "10 ton", "500 kg" ya da "200 adet".',
        "ask_price": 'Fiyat nedir? Ör. "tonu 1000 euro" ya da "toplam 10.000 euro".',
        "unknown_product": (
            '"{product}" için bir tarife kodu bulamadım. Ürünün İngilizce adını ya da '
            'GTİP kodunu yazmayı deneyin (ör. "kod 0808.10").'
        ),
        "unit_mismatch": (
            "Fiyat {price_unit} başına, miktar ise {unit} cinsinden. İkisini aynı birimle yazın."
        ),
        "intro": "{origin} menşeli {product} için tahmini hesap:",
        "intra_eu": (
            "{origin} bir AB üyesi; oradan AB'ye gelen mallardan gümrük vergisi alınmaz "
            "(AB içi ticaret)."
        ),
        "non_eu_destination": (
            "Not: Bu hesap AB gümrük tarifesine göredir. {destination} ithalat vergileri bu "
            "sistemde yok."
        ),
        "no_rate": (
            "Bu sistemde {code} için kayıtlı bir vergi oranı yok, bu yüzden vergi tutarını "
            "veremiyorum. Mal bedeli yukarıda; oranı AB TARIC veritabanından kontrol edin."
        ),
        "assumed_total": (
            '{amount} tutarını toplam fiyat olarak aldım. Birim fiyatsa ör. "tonu 1000 euro" '
            "şeklinde yazın."
        ),
        "currency_note": (
            "AB gümrük vergisi EUR üzerinden hesaplanır; tutarlar {currency} olarak gösterildi, "
            "resmi gümrük kuru farklı olabilir."
        ),
        "disclaimer": "Tahmini hesaptır: ithalat KDV'si, navlun, sigorta ve diğer masraflar dahil değildir.",
        "classify_intro": '"{product}" için en yakın kodlar:',
        "screen_none": '"{name}" için yaptırım listesinde eşleşme yok.',
        "screen_hits": '"{name}" için olası yaptırım listesi eşleşmeleri:',
        "screen_ask": "Hangi kişi ya da firmayı tarayayım? Adını yazın.",
        "help": (
            "Gümrük vergisi tahmini yapabilir, GTİP bulabilir ve isim tarayabilirim. Örnek: "
            '"Türkiye\'den 10 ton elma, tonu 1000 euro, maliyeti hesapla".'
        ),
        "goods_value": "Mal bedeli",
        "duty": "Gümrük vergisi",
        "total": "Toplam",
        "rate": "Oran",
    },
    "de": {
        "ask_product": 'Um welche Ware geht es? Nennen Sie das Produkt (z. B. "Äpfel") oder die KN-Nummer.',
        "ask_origin": "Aus welchem Land kommt die Ware?",
        "ask_quantity": 'Welche Menge? Zum Beispiel "10 t", "500 kg" oder "200 Stück".',
        "ask_price": 'Wie hoch ist der Preis? Zum Beispiel "1000 EUR pro Tonne" oder "insgesamt 10.000 EUR".',
        "unknown_product": (
            'Für "{product}" habe ich keine Zolltarifnummer gefunden. Versuchen Sie den '
            'englischen Namen oder geben Sie die KN-Nummer an (z. B. "Code 0808.10").'
        ),
        "unit_mismatch": (
            "Der Preis gilt pro {price_unit}, die Menge ist in {unit}. Bitte beides in "
            "derselben Einheit angeben."
        ),
        "intro": "Schätzung für {product} aus {origin}:",
        "intra_eu": (
            "{origin} ist EU-Mitglied; Waren von dort in die EU sind zollfrei "
            "(innergemeinschaftlicher Handel)."
        ),
        "non_eu_destination": (
            "Hinweis: Diese Berechnung nutzt den EU-Zolltarif. Einfuhrabgaben für "
            "{destination} sind in diesem System nicht enthalten."
        ),
        "no_rate": (
            "Für {code} ist in diesem System kein Zollsatz hinterlegt, daher kann ich den "
            "Zoll nicht angeben. Der Warenwert steht oben; prüfen Sie den Satz in TARIC."
        ),
        "assumed_total": (
            "Ich habe {amount} als Gesamtpreis genommen. Ist es ein Stückpreis, schreiben Sie "
            'z. B. "1000 EUR pro Tonne".'
        ),
        "currency_note": (
            "Der EU-Zoll wird in EUR bemessen; die Beträge sind in {currency} angegeben, "
            "der amtliche Zollkurs kann abweichen."
        ),
        "disclaimer": (
            "Nur eine Schätzung: Einfuhrumsatzsteuer, Fracht, Versicherung und weitere "
            "Kosten sind nicht enthalten."
        ),
        "classify_intro": 'Die passendsten Codes für "{product}":',
        "screen_none": 'Kein Treffer auf der Sanktionsliste für "{name}".',
        "screen_hits": 'Mögliche Treffer auf der Sanktionsliste für "{name}":',
        "screen_ask": "Welche Person oder Firma soll ich prüfen? Schreiben Sie den Namen.",
        "help": (
            "Ich schätze Zölle, finde KN-Nummern und prüfe Namen. Beispiel: "
            '"10 t Äpfel aus der Türkei, 1000 EUR pro Tonne".'
        ),
        "goods_value": "Warenwert",
        "duty": "Zoll",
        "total": "Gesamt",
        "rate": "Satz",
    },
}


SUGGESTIONS = {
    "en": [
        "10 t of apples from Turkey, 1000 EUR per tonne, calculate the cost",
        "500 t-shirts from China, 4 EUR each",
        "Which code is a laptop?",
    ],
    "tr": [
        "Türkiye'den 10 ton elma, tonu 1000 euro, maliyeti hesapla",
        "Çin'den 500 adet tişört, tanesi 4 euro",
        "Dizüstü bilgisayarın GTİP kodu nedir?",
    ],
    "de": [
        "10 t Äpfel aus der Türkei, 1000 EUR pro Tonne, Kosten berechnen",
        "500 T-Shirts aus China, 4 EUR pro Stück",
        "Welche Nummer hat ein Laptop?",
    ],
}


#: (keywords, answers per language). Keywords are matched as substrings of the
#: normalized message in any language; the best-scoring entry wins.
FAQ: list[tuple[tuple[str, ...], dict[str, str]]] = [
    (
        ("şifre", "parola", "password", "passwort", "unuttum", "forgot", "vergessen", "reset"),
        {
            "en": "Password resets are not self-service yet. Write to support@customsiq.org from the e-mail you registered with, or sign in with Google if that address is a Google account.",
            "tr": "Parola sıfırlama henüz kendi kendine yapılamıyor. Kayıtlı e-postanızdan support@customsiq.org adresine yazın ya da adresiniz bir Google hesabıysa Google ile giriş yapın.",
            "de": "Das Zurücksetzen des Passworts ist noch nicht selbst möglich. Schreiben Sie von Ihrer registrierten Adresse an support@customsiq.org oder melden Sie sich mit Google an.",
        },
    ),
    (
        ("google",),
        {
            "en": 'On the sign-in page choose "Continue with Google". The first time, your account is created immediately, with no code needed.',
            "tr": 'Giriş sayfasında "Google ile devam et"i seçin. İlk girişte hesabınız hemen oluşturulur, kod gerekmez.',
            "de": 'Wählen Sie auf der Anmeldeseite "Weiter mit Google". Beim ersten Mal wird Ihr Konto sofort angelegt, ohne Code.',
        },
    ),
    (
        (
            "kayıt",
            "üye",
            "hesap aç",
            "register",
            "sign up",
            "signup",
            "account",
            "registrier",
            "konto",
            "kod gelmedi",
            "code",
            "doğrulama",
            "verification",
        ),
        {
            "en": 'Register on the sign-in page with a username, e-mail and password. We e-mail you a 6-digit code, valid for 10 minutes. If it doesn\'t arrive, check spam and use "Resend code" after 60 seconds.',
            "tr": 'Giriş sayfasında kullanıcı adı, e-posta ve parolayla kaydolun. E-postanıza 10 dakika geçerli 6 haneli bir kod gelir. Gelmezse spam klasörüne bakın, 60 saniye sonra "Kodu tekrar gönder"e basın.',
            "de": 'Registrieren Sie sich auf der Anmeldeseite mit Benutzername, E-Mail und Passwort. Sie erhalten einen 6-stelligen Code (10 Minuten gültig). Kommt er nicht an, prüfen Sie den Spam-Ordner und nutzen Sie nach 60 Sekunden "Code erneut senden".',
        },
    ),
    (
        (
            "ara",
            "arama",
            "search",
            "such",
            "bul",
            "find",
            "nasıl kullan",
            "how do i use",
            "wie benutze",
        ),
        {
            "en": 'In "HS / CN code search", describe the goods in plain words (e.g. "cotton t-shirt") or type a code. Results show the code, its place in the tariff and a match score.',
            "tr": '"HS / CN kodu arama" kartında eşyayı sade bir dille yazın (ör. "pamuklu tişört") ya da kodu girin. Sonuçlarda kod, tarifedeki yeri ve eşleşme puanı görünür. Türkçe ürün adları için bu sohbet asistanı daha iyi sonuç verir.',
            "de": 'Beschreiben Sie in der "HS-/KN-Code-Suche" die Ware in einfachen Worten (z. B. "Baumwoll-T-Shirt") oder geben Sie einen Code ein. Die Ergebnisse zeigen Code, Position im Tarif und Trefferquote.',
        },
    ),
    (
        (
            "gtip",
            "gtıp",
            "hs kod",
            "cn kod",
            "nedir",
            "what is a cn",
            "what is hs",
            "was ist",
            "kn-nummer",
            "combined nomenclature",
        ),
        {
            "en": "HS is the 6-digit international tariff code; the EU's CN adds 2 digits (8), and TARIC 2 more (10). CustomsIQ searches the EU Combined Nomenclature 2026.",
            "tr": "HS 6 haneli uluslararası tarife kodudur; AB'nin CN'si buna 2 hane ekler (8), TARIC 2 hane daha (10). Türkiye'deki GTİP 12 hanelidir. CustomsIQ, AB Kombine Nomenklatürü 2026'da arama yapar.",
            "de": "HS ist der 6-stellige internationale Zolltarifcode; die KN der EU fügt 2 Stellen hinzu (8), TARIC weitere 2 (10). CustomsIQ durchsucht die Kombinierte Nomenklatur 2026.",
        },
    ),
    (
        ("hs-6", "hs6", "8 hane", "8-digit", "8-stellig", "detay yok", "detail not"),
        {
            "en": 'Codes marked "HS-6" come from the international HS 2022 list because the EU file lacks that heading. The EU 8-digit detail for them is not in this data.',
            "tr": '"HS-6" etiketli kodlar, AB dosyasında o başlık olmadığı için uluslararası HS 2022 listesinden gelir. Bu kodların AB 8 haneli ayrıntısı bu veride yok.',
            "de": 'Mit "HS-6" markierte Codes stammen aus der internationalen HS-2022-Liste, weil die EU-Datei diese Position nicht enthält. Die 8-stellige EU-Unterteilung fehlt dafür.',
        },
    ),
    (
        ("yaptırım", "tarama", "sanction", "screen", "sanktion", "embargo", "kara liste"),
        {
            "en": '"Sanctions screening" checks a person or company name against the OFAC SDN list. It tolerates word order and partial company names; every hit needs human review.',
            "tr": '"Yaptırım taraması", bir kişi ya da firma adını OFAC SDN listesine karşı kontrol eder. Kelime sırası ve kısmi firma adlarına toleranslıdır; her eşleşme insan tarafından incelenmelidir.',
            "de": 'Die "Sanktionsprüfung" gleicht einen Personen- oder Firmennamen mit der OFAC-SDN-Liste ab. Sie toleriert Wortreihenfolge und Teilnamen; jeder Treffer braucht eine menschliche Prüfung.',
        },
    ),
    (
        ("vergi", "gümrük vergisi", "maliyet", "duty", "cost", "zoll", "kosten", "hesapla"),
        {
            "en": 'Use the "Ask a question" card: write e.g. "10 t of apples from Turkey, 1000 EUR per tonne". The duty uses the EU tariff; only rates on record in this system are applied.',
            "tr": '"Soru sor" kartını kullanın: ör. "Türkiye\'den 10 ton elma, tonu 1000 euro, maliyeti hesapla" yazın. Hesap AB tarifesine göredir; yalnızca sistemde kayıtlı oranlar uygulanır.',
            "de": 'Nutzen Sie die Karte "Frage stellen": z. B. "10 t Äpfel aus der Türkei, 1000 EUR pro Tonne". Berechnet wird nach EU-Tarif; nur hinterlegte Sätze werden angewandt.',
        },
    ),
    (
        ("fatura", "invoice", "rechnung", "pdf", "yükle", "upload", "hochladen"),
        {
            "en": '"Invoice extraction" reads a PDF invoice (max 2 MB) and pre-fills the forms. The file is never stored. Scanned PDFs without a text layer cannot be read.',
            "tr": '"Fatura okuma", PDF faturayı (en fazla 2 MB) okur ve formları doldurur. Dosya saklanmaz. Metin katmanı olmayan taranmış PDF\'ler okunamaz.',
            "de": 'Die "Rechnungserfassung" liest eine PDF-Rechnung (max. 2 MB) und füllt die Formulare vor. Die Datei wird nicht gespeichert. Gescannte PDFs ohne Textebene sind nicht lesbar.',
        },
    ),
    (
        (
            "rol",
            "role",
            "rolle",
            "yetki",
            "permission",
            "berechtigung",
            "inceleme",
            "review",
            "onay",
            "viewer",
            "analyst",
        ),
        {
            "en": 'New accounts are "viewer" (read-only). Signing off results needs a higher role: analyst for classification and duty, compliance officer for screening. The site owner assigns roles.',
            "tr": 'Yeni hesaplar "viewer" (salt okunur) rolündedir. Sonuçları onaylamak için daha yüksek rol gerekir: sınıflandırma ve vergi için analist, tarama için uyum sorumlusu. Rolleri site sahibi verir.',
            "de": 'Neue Konten sind "viewer" (nur lesen). Zum Freigeben braucht es eine höhere Rolle: Analyst für Einreihung und Zoll, Compliance-Beauftragte/r für Prüfungen. Rollen vergibt der Inhaber.',
        },
    ),
    (
        ("dil", "language", "sprache", "türkçe", "english", "deutsch", "ingilizce", "almanca"),
        {
            "en": "Switch language with EN / TR / DE at the top right. Your choice is remembered in this browser.",
            "tr": "Sağ üstteki EN / TR / DE düğmeleriyle dili değiştirin. Seçiminiz bu tarayıcıda hatırlanır.",
            "de": "Wechseln Sie die Sprache oben rechts mit EN / TR / DE. Die Wahl wird in diesem Browser gespeichert.",
        },
    ),
    (
        ("veri", "kaynak", "data", "source", "quelle", "daten", "güncel", "up to date", "aktuell"),
        {
            "en": "Codes: EU Combined Nomenclature 2026 plus the WCO HS 2022 list for missing headings. Sanctions: OFAC SDN. Duty rates: a small sample only, so many codes have no rate on record.",
            "tr": "Kodlar: AB Kombine Nomenklatürü 2026 ve eksik başlıklar için WCO HS 2022 listesi. Yaptırımlar: OFAC SDN. Vergi oranları: yalnızca küçük bir örnek set, bu yüzden birçok kodda kayıtlı oran yok.",
            "de": "Codes: Kombinierte Nomenklatur 2026 plus WCO-HS-2022-Liste für fehlende Positionen. Sanktionen: OFAC SDN. Zollsätze: nur eine kleine Auswahl, daher fehlt bei vielen Codes ein Satz.",
        },
    ),
    (
        (
            "gizlilik",
            "kayıt altına",
            "privacy",
            "datenschutz",
            "log",
            "izleme",
            "tracking",
            "kişisel veri",
        ),
        {
            "en": "Searches and actions are logged to run the service and kept for 90 days. Passwords, verification codes, invoice contents and IP addresses are never stored.",
            "tr": "Hizmetin işletilmesi için aramalar ve işlemler kayıt altına alınır ve 90 gün saklanır. Parolalar, doğrulama kodları, fatura içerikleri ve IP adresleri asla saklanmaz.",
            "de": "Suchen und Aktionen werden zum Betrieb protokolliert und 90 Tage aufbewahrt. Passwörter, Codes, Rechnungsinhalte und IP-Adressen werden nie gespeichert.",
        },
    ),
    (
        (
            "iletişim",
            "destek",
            "contact",
            "support",
            "kontakt",
            "e-posta",
            "email",
            "mail",
            "insan",
            "human",
        ),
        {
            "en": "You can reach us at support@customsiq.org.",
            "tr": "Bize support@customsiq.org adresinden ulaşabilirsiniz.",
            "de": "Sie erreichen uns unter support@customsiq.org.",
        },
    ),
    (
        ("çıkış", "logout", "sign out", "abmelden", "oturumu kapat"),
        {
            "en": 'Use "Sign out" at the top right. Sessions also expire on their own after 12 hours.',
            "tr": 'Sağ üstteki "Çıkış yap"ı kullanın. Oturumlar 12 saat sonra kendiliğinden de sona erer.',
            "de": 'Nutzen Sie oben rechts "Abmelden". Sitzungen laufen nach 12 Stunden auch von selbst ab.',
        },
    ),
]

SUPPORT_FALLBACK = {
    "en": "I didn't find an answer to that. Pick a topic below, or write to support@customsiq.org.",
    "tr": "Buna bir cevap bulamadım. Aşağıdan bir konu seçin ya da support@customsiq.org adresine yazın.",
    "de": "Dazu habe ich keine Antwort gefunden. Wählen Sie unten ein Thema oder schreiben Sie an support@customsiq.org.",
}

SUPPORT_SUGGESTIONS = {
    "en": [
        "How do I search for a code?",
        "I forgot my password",
        "How is duty calculated?",
        "What does HS-6 mean?",
    ],
    "tr": [
        "Kod araması nasıl yapılır?",
        "Şifremi unuttum",
        "Vergi nasıl hesaplanır?",
        "HS-6 ne demek?",
    ],
    "de": [
        "Wie suche ich einen Code?",
        "Passwort vergessen",
        "Wie wird der Zoll berechnet?",
        "Was bedeutet HS-6?",
    ],
}
