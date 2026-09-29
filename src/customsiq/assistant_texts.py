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
        "disclaimer": (
            "Estimate only: duty rates in CustomsIQ are demo data, not official rates, and "
            "import VAT, freight, insurance and other charges are not included."
        ),
        "classify_intro": 'The closest codes for "{product}":',
        "screen_none": 'No sanctions-list match for "{name}".',
        "screen_hits": 'Possible sanctions-list matches for "{name}":',
        "screen_ask": "Which person or company should I screen? Write the name.",
        "help": (
            "I can estimate customs duty, find a CN code and screen a name. Try: "
            '"10 t of apples from Turkey, 1000 EUR per tonne".'
        ),
        "hello": (
            "Hello! I'm the CustomsIQ assistant (rule-based, no AI). I can estimate EU customs "
            "duty for a shipment, suggest a CN code for goods, and screen a name against the "
            'sanctions list. Tell me the goods first, e.g. "10 t of apples from Turkey, '
            '1000 EUR per tonne".'
        ),
        "capabilities": (
            "Here is what I can do: 1) estimate EU customs duty: tell me the goods, where they "
            'come from and the price; 2) suggest a CN code: "which code is a laptop?"; '
            "3) screen a name: 'sanctions check \"Example Trading Co\"'. I follow fixed rules, "
            "so plain, specific sentences work best."
        ),
        "thanks": "You're welcome. Ask me about another shipment any time.",
        "retry_product": (
            'I couldn\'t find the goods in "{text}". Name the product in a few words '
            '(e.g. "steel screws", "cotton t-shirts") or give its CN code (e.g. "code 7318.15").'
        ),
        "retry_origin": (
            'I couldn\'t recognise a country in "{text}". Write the country the goods come '
            'from, e.g. "from China" or "Turkey".'
        ),
        "retry_price": (
            'I couldn\'t read a price in "{text}". Write an amount with its currency, e.g. '
            '"1.2 million USD", "250,000 EUR in total" or "4 EUR each".'
        ),
        "retry_quantity": (
            'I couldn\'t read a quantity in "{text}". Write a number with its unit, e.g. '
            '"10 t", "500 kg" or "200 pieces".'
        ),
        "start_over": (
            'You can also write the whole question in one sentence, e.g. "500 t-shirts from '
            'China, 4 EUR each".'
        ),
        "eu_destination": (
            "{destination} is an EU member state, so the common EU customs tariff applies."
        ),
        "low_confidence_code": (
            "The code {code} is only a low-confidence lead for these goods; check it before "
            "relying on this estimate."
        ),
        "currency_as_given": (
            "The duty is computed on the amount as given, in {currency}. CustomsIQ does not "
            "convert currencies."
        ),
        "currency_assumed": (
            "No currency was given, so the amount is used exactly as written (shown as EUR). "
            "CustomsIQ does not convert currencies."
        ),
        "classify_lead": (
            'I\'m not confident about "{product}". The best lead is {code} — {description}. '
            "Treat it as a lead only: describe the goods more precisely (material, use) or "
            "give the CN code."
        ),
        "other_leads": "Other leads:",
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
        "disclaimer": (
            "Tahmini hesaptır: CustomsIQ'daki vergi oranları resmi değil, demo verisidir; "
            "ithalat KDV'si, navlun, sigorta ve diğer masraflar dahil değildir."
        ),
        "classify_intro": '"{product}" için en yakın kodlar:',
        "screen_none": '"{name}" için yaptırım listesinde eşleşme yok.',
        "screen_hits": '"{name}" için olası yaptırım listesi eşleşmeleri:',
        "screen_ask": "Hangi kişi ya da firmayı tarayayım? Adını yazın.",
        "help": (
            "Gümrük vergisi tahmini yapabilir, GTİP bulabilir ve isim tarayabilirim. Örnek: "
            '"Türkiye\'den 10 ton elma, tonu 1000 euro, maliyeti hesapla".'
        ),
        "hello": (
            "Merhaba! Ben CustomsIQ asistanıyım (kurallı, yapay zekâ yok). Bir sevkiyat için AB "
            "gümrük vergisini tahmin edebilir, eşya için GTİP/CN kodu önerebilir ve bir ismi "
            "yaptırım listesinde tarayabilirim. Önce ürünü yazın, ör. \"Türkiye'den 10 ton "
            'elma, tonu 1000 euro".'
        ),
        "capabilities": (
            "Yapabileceklerim: 1) AB gümrük vergisi tahmini: ürünü, nereden geldiğini ve "
            'fiyatını yazın; 2) CN kodu önerisi: "dizüstü bilgisayarın GTİP kodu nedir?"; '
            "3) isim taraması: 'yaptırım taraması \"Example Trading Co\"'. Sabit kurallarla "
            "çalışırım; kısa ve net cümleler en iyi sonucu verir."
        ),
        "thanks": "Rica ederim. Başka bir sevkiyat için istediğiniz zaman sorabilirsiniz.",
        "retry_product": (
            '"{text}" içinde ürünü bulamadım. Ürünü birkaç kelimeyle yazın (ör. "çelik vida", '
            '"pamuklu tişört") ya da GTİP kodunu verin (ör. "kod 7318.15").'
        ),
        "retry_origin": (
            '"{text}" içinde bir ülke tanıyamadım. Malın geldiği ülkeyi yazın, ör. '
            '"Çin\'den" ya da "Türkiye".'
        ),
        "retry_price": (
            '"{text}" içinde bir fiyat okuyamadım. Tutarı para birimiyle yazın, ör. '
            '"1,2 milyon dolar", "toplam 250.000 euro" ya da "tanesi 4 euro".'
        ),
        "retry_quantity": (
            '"{text}" içinde bir miktar okuyamadım. Sayıyı birimiyle yazın, ör. "10 ton", '
            '"500 kg" ya da "200 adet".'
        ),
        "start_over": (
            "Sorunun tamamını tek cümlede de yazabilirsiniz, ör. \"Çin'den 500 adet tişört, "
            'tanesi 4 euro".'
        ),
        "eu_destination": "{destination} bir AB üyesi; bu yüzden ortak AB gümrük tarifesi uygulanır.",
        "low_confidence_code": (
            "{code} kodu bu eşya için yalnızca düşük güvenli bir ipucudur; bu tahmine "
            "güvenmeden önce kodu kontrol edin."
        ),
        "currency_as_given": (
            "Vergi, verilen tutar üzerinden {currency} cinsinden hesaplandı. CustomsIQ döviz "
            "çevirisi yapmaz."
        ),
        "currency_assumed": (
            "Para birimi belirtilmedi; tutar yazıldığı gibi kullanıldı (EUR olarak gösterildi). "
            "CustomsIQ döviz çevirisi yapmaz."
        ),
        "classify_lead": (
            '"{product}" konusunda emin değilim. En iyi ipucu {code} — {description}. Bunu '
            "yalnızca ipucu olarak alın: eşyayı daha ayrıntılı tarif edin (malzeme, kullanım) "
            "ya da GTİP kodunu verin."
        ),
        "other_leads": "Diğer ipuçları:",
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
        "disclaimer": (
            "Nur eine Schätzung: Die Zollsätze in CustomsIQ sind Demodaten, keine amtlichen "
            "Sätze; Einfuhrumsatzsteuer, Fracht, Versicherung und weitere Kosten sind nicht "
            "enthalten."
        ),
        "classify_intro": 'Die passendsten Codes für "{product}":',
        "screen_none": 'Kein Treffer auf der Sanktionsliste für "{name}".',
        "screen_hits": 'Mögliche Treffer auf der Sanktionsliste für "{name}":',
        "screen_ask": "Welche Person oder Firma soll ich prüfen? Schreiben Sie den Namen.",
        "help": (
            "Ich schätze Zölle, finde KN-Nummern und prüfe Namen. Beispiel: "
            '"10 t Äpfel aus der Türkei, 1000 EUR pro Tonne".'
        ),
        "hello": (
            "Hallo! Ich bin der CustomsIQ-Assistent (regelbasiert, keine KI). Ich schätze den "
            "EU-Zoll für eine Sendung, schlage eine KN-Nummer für Waren vor und prüfe einen "
            'Namen gegen die Sanktionsliste. Nennen Sie zuerst die Ware, z. B. "10 t Äpfel aus '
            'der Türkei, 1000 EUR pro Tonne".'
        ),
        "capabilities": (
            "Das kann ich: 1) EU-Zoll schätzen: nennen Sie Ware, Herkunftsland und Preis; "
            '2) KN-Nummer vorschlagen: "Welche Nummer hat ein Laptop?"; 3) Namen prüfen: '
            "'Sanktionsprüfung \"Example Trading Co\"'. Ich arbeite mit festen Regeln, klare "
            "kurze Sätze funktionieren am besten."
        ),
        "thanks": "Gern geschehen. Fragen Sie jederzeit zu einer weiteren Sendung.",
        "retry_product": (
            'In "{text}" habe ich keine Ware gefunden. Nennen Sie das Produkt in wenigen Worten '
            '(z. B. "Stahlschrauben", "Baumwoll-T-Shirts") oder die KN-Nummer (z. B. "Code 7318.15").'
        ),
        "retry_origin": (
            'In "{text}" habe ich kein Land erkannt. Schreiben Sie das Herkunftsland, z. B. '
            '"aus China" oder "Türkei".'
        ),
        "retry_price": (
            'In "{text}" habe ich keinen Preis gefunden. Schreiben Sie Betrag und Währung, '
            'z. B. "1,2 Mio. USD", "insgesamt 250.000 EUR" oder "4 EUR pro Stück".'
        ),
        "retry_quantity": (
            'In "{text}" habe ich keine Menge gefunden. Schreiben Sie Zahl und Einheit, z. B. '
            '"10 t", "500 kg" oder "200 Stück".'
        ),
        "start_over": (
            'Sie können die ganze Frage auch in einem Satz schreiben, z. B. "500 T-Shirts aus '
            'China, 4 EUR pro Stück".'
        ),
        "eu_destination": (
            "{destination} ist EU-Mitglied, daher gilt der gemeinsame EU-Zolltarif."
        ),
        "low_confidence_code": (
            "Die Nummer {code} ist für diese Ware nur ein unsicherer Hinweis; prüfen Sie sie, "
            "bevor Sie sich auf diese Schätzung verlassen."
        ),
        "currency_as_given": (
            "Der Zoll wird auf den angegebenen Betrag in {currency} berechnet. CustomsIQ rechnet "
            "keine Währungen um."
        ),
        "currency_assumed": (
            "Es wurde keine Währung genannt; der Betrag wird so verwendet, wie er geschrieben "
            "wurde (als EUR angezeigt). CustomsIQ rechnet keine Währungen um."
        ),
        "classify_lead": (
            'Bei "{product}" bin ich mir nicht sicher. Der beste Hinweis ist {code} — '
            "{description}. Nur als Hinweis verstehen: beschreiben Sie die Ware genauer "
            "(Material, Verwendung) oder nennen Sie die KN-Nummer."
        ),
        "other_leads": "Weitere Hinweise:",
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
            "en": 'CustomsIQ has no password-reset function. If your e-mail address is a Google account, use "Continue with Google" on the sign-in page. Otherwise write to support@customsiq.org from the address you registered with; this is handled by a person, not an automatic reset.',
            "tr": 'CustomsIQ\'da parola sıfırlama özelliği yoktur. E-posta adresiniz bir Google hesabıysa giriş sayfasında "Google ile devam et"i kullanın. Değilse kayıtlı adresinizden support@customsiq.org adresine yazın; talebi bir kişi inceler, otomatik sıfırlama yoktur.',
            "de": 'CustomsIQ hat keine Funktion zum Zurücksetzen des Passworts. Ist Ihre Adresse ein Google-Konto, nutzen Sie auf der Anmeldeseite "Weiter mit Google". Andernfalls schreiben Sie von Ihrer registrierten Adresse an support@customsiq.org; das bearbeitet ein Mensch, ein automatisches Zurücksetzen gibt es nicht.',
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
            "en": 'Use the "Ask a question" card: write e.g. "10 t of apples from Turkey, 1000 EUR per tonne". The codes come from the real EU Combined Nomenclature, but the duty rates in CustomsIQ are demo data, so the result is an illustration, not an official duty. Amounts are used in the currency you give; nothing is converted.',
            "tr": '"Soru sor" kartını kullanın: ör. "Türkiye\'den 10 ton elma, tonu 1000 euro, maliyeti hesapla" yazın. Kodlar gerçek AB Kombine Nomenklatüründen gelir, ancak CustomsIQ\'daki vergi oranları demo verisidir; sonuç resmi vergi değil, bir örnektir. Tutarlar verdiğiniz para biriminde kullanılır, çeviri yapılmaz.',
            "de": 'Nutzen Sie die Karte "Frage stellen": z. B. "10 t Äpfel aus der Türkei, 1000 EUR pro Tonne". Die Codes stammen aus der echten Kombinierten Nomenklatur der EU, die Zollsätze in CustomsIQ sind aber Demodaten; das Ergebnis ist eine Veranschaulichung, kein amtlicher Zoll. Beträge werden in der angegebenen Währung verwendet, nichts wird umgerechnet.',
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
            "en": "Codes: EU Combined Nomenclature 2026 plus the WCO HS 2022 list for missing headings. Sanctions: OFAC SDN. Duty rates and trade agreements: a small set of fictional demo data, not official rates, so many codes have no rate on record.",
            "tr": "Kodlar: AB Kombine Nomenklatürü 2026 ve eksik başlıklar için WCO HS 2022 listesi. Yaptırımlar: OFAC SDN. Vergi oranları ve ticaret anlaşmaları: küçük, kurgusal bir demo seti, resmi oran değil; bu yüzden birçok kodda kayıtlı oran yok.",
            "de": "Codes: Kombinierte Nomenklatur 2026 plus WCO-HS-2022-Liste für fehlende Positionen. Sanktionen: OFAC SDN. Zollsätze und Handelsabkommen: eine kleine, fiktive Demo-Auswahl, keine amtlichen Sätze; daher fehlt bei vielen Codes ein Satz.",
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
        "Forgot my password?",
        "How is duty calculated?",
        "What does HS-6 mean?",
    ],
    "tr": [
        "Kod araması nasıl yapılır?",
        "Şifremi unuttum?",
        "Vergi nasıl hesaplanır?",
        "HS-6 ne demek?",
    ],
    "de": [
        "Wie suche ich einen Code?",
        "Passwort vergessen?",
        "Wie wird der Zoll berechnet?",
        "Was bedeutet HS-6?",
    ],
}


#: Whole-message small talk, matched on word boundaries in any UI language; the
#: reply itself follows the UI language. A message counts as small talk only when
#: nothing but these phrases and SMALLTALK_FILLER is left, so "hi, 10 t apples"
#: is still a shipment.
SMALLTALK: dict[str, tuple[str, ...]] = {
    "greeting": (
        "hi",
        "hii",
        "hello",
        "hey",
        "hiya",
        "howdy",
        "yo",
        "good morning",
        "good afternoon",
        "good evening",
        "hi there",
        "hello there",
        "merhaba",
        "merhabalar",
        "mrb",
        "selam",
        "selamlar",
        "slm",
        "günaydın",
        "iyi günler",
        "iyi akşamlar",
        "kolay gelsin",
        "hallo",
        "servus",
        "moin",
        "guten tag",
        "guten morgen",
        "guten abend",
        "grüß gott",
        "grüezi",
        "hola",
        "salut",
        "how are you",
        "nasılsın",
        "wie geht's",
        "wie geht es dir",
    ),
    "help": (
        "help",
        "help me",
        "what can you do",
        "what do you do",
        "who are you",
        "how does this work",
        "how do you work",
        "what is this",
        "what are you",
        "yardım",
        "yardım et",
        "yardımcı ol",
        "ne yapabilirsin",
        "neler yapabilirsin",
        "ne işe yarıyorsun",
        "sen kimsin",
        "nasıl çalışıyorsun",
        "bu ne",
        "hilfe",
        "was kannst du",
        "was machst du",
        "wer bist du",
        "wie funktioniert das",
        "was ist das",
    ),
    "thanks": (
        "thanks",
        "thank you",
        "thx",
        "ty",
        "cheers",
        "great",
        "bye",
        "goodbye",
        "see you",
        "teşekkürler",
        "teşekkür ederim",
        "teşekkür",
        "tşk",
        "sağol",
        "sağ ol",
        "sağolun",
        "eyvallah",
        "görüşürüz",
        "hoşçakal",
        "hoşça kal",
        "danke",
        "danke schön",
        "dankeschön",
        "vielen dank",
        "merci",
        "tschüss",
        "auf wiedersehen",
        "super",
    ),
}

#: Words allowed around small talk ("hi there bot", "ok thanks", "bitte hilfe").
SMALLTALK_FILLER = (
    "ok",
    "okay",
    "please",
    "pls",
    "there",
    "bot",
    "assistant",
    "customsiq",
    "you",
    "me",
    "can",
    "could",
    "i",
    "need",
    "a",
    "the",
    "so",
    "much",
    "very",
    "lot",
    "and",
    "oh",
    "well",
    "all",
    "tamam",
    "peki",
    "lütfen",
    "bana",
    "çok",
    "ve",
    "mısın",
    "misin",
    "bitte",
    "mir",
    "du",
    "sie",
    "und",
    "ja",
    "gut",
    "vielen",
)

#: The help bubble's small-talk replies: what it can help with, in each language.
SUPPORT_SMALLTALK: dict[str, dict[str, str]] = {
    "greeting": {
        "en": 'Hi! I answer questions about using CustomsIQ: code search, sign-up and sign-in, roles, invoices, data sources and privacy. Pick a topic below or type your question. For a duty estimate, use the "Ask a question" card.',
        "tr": 'Merhaba! CustomsIQ\'yu kullanmayla ilgili soruları yanıtlarım: kod arama, kayıt ve giriş, roller, faturalar, veri kaynakları ve gizlilik. Aşağıdan bir konu seçin ya da sorunuzu yazın. Vergi tahmini için "Soru sor" kartını kullanın.',
        "de": 'Hallo! Ich beantworte Fragen zur Nutzung von CustomsIQ: Code-Suche, Registrierung und Anmeldung, Rollen, Rechnungen, Datenquellen und Datenschutz. Wählen Sie unten ein Thema oder stellen Sie Ihre Frage. Für eine Zollschätzung nutzen Sie die Karte "Frage stellen".',
    },
    "help": {
        "en": 'I can help with: searching for a code, signing up and signing in (including Google), roles and reviews, invoice extraction, where the data comes from, and privacy. Pick a topic below or type your question. Duty estimates are in the "Ask a question" card.',
        "tr": 'Şu konularda yardımcı olabilirim: kod arama, kayıt ve giriş (Google dahil), roller ve incelemeler, fatura okuma, verilerin kaynağı ve gizlilik. Aşağıdan bir konu seçin ya da sorunuzu yazın. Vergi tahmini "Soru sor" kartındadır.',
        "de": 'Ich helfe bei: Code-Suche, Registrierung und Anmeldung (auch mit Google), Rollen und Prüfungen, Rechnungserfassung, Datenquellen und Datenschutz. Wählen Sie unten ein Thema oder stellen Sie Ihre Frage. Zollschätzungen gibt es in der Karte "Frage stellen".',
    },
    "thanks": {
        "en": "You're welcome! Ask again any time.",
        "tr": "Rica ederim! İstediğiniz zaman tekrar sorun.",
        "de": "Gern geschehen! Fragen Sie jederzeit wieder.",
    },
}
