QUESTION_TEMPLATES = {
    "taraf_isci":           "İşçinin (çalışanın) adı soyadı ve TC kimlik numarası nedir?",
    "taraf_isveren":        "İşverenin ticaret unvanı ve vergi numarası nedir?",
    "taraf_kiraci":         "Kiracının adı soyadı ve TC kimlik numarası nedir?",
    "taraf_kiraya_veren":   "Kiraya verenin adı soyadı ve iletişim bilgileri nedir?",
    "taraf_alici":          "Alıcının adı soyadı veya ticaret unvanı nedir?",
    "taraf_satici":         "Satıcının adı soyadı veya ticaret unvanı nedir?",
    "taraf_1":              "Birinci tarafın tam adı veya ticaret unvanı nedir?",
    "taraf_2":              "İkinci tarafın tam adı veya ticaret unvanı nedir?",
    "muvekkil":             "Müvekkilin adı soyadı nedir?",
    "vekil":                "Vekilin adı soyadı nedir?",
    "kefil":                "Kefilin adı soyadı ve TC kimlik numarası nedir?",
    "alacakli":             "Alacaklının adı soyadı veya ticaret unvanı nedir?",

    "ucret":                "Çalışanın aylık brüt ücreti nedir? (Ödeme günü ve yöntemi de eklenebilir)",
    "kira_bedeli":          "Aylık kira bedeli nedir? Ödeme günü ve yöntemi nedir?",
    "satis_bedeli":         "Satış bedeli nedir? Ödeme planı var mı?",
    "hizmet_bedeli":        "Hizmet bedeli nedir? Nasıl ödenecek?",
    "kefalet_miktari":      "Kefalet miktarı nedir?",

    "baslangic_tarihi":     "Sözleşme ne zaman başlayacak?",
    "bitis_tarihi":         "Sözleşmenin bitiş tarihi var mı?",
    "teslim_tarihi":        "Teslim tarihi ne zaman?",

    "is_tanimi":            "Çalışanın pozisyonu ve görev tanımı nedir?",
    "hizmet_tanimi":        "Sağlanacak hizmetin kapsamı nedir?",
    "calisma_yeri":         "İş yerinin adresi nedir? Uzaktan çalışma söz konusu mu?",
    "kiralanan_adres":      "Kiralanan taşınmazın tam adresi nedir?",
    "teslim_yeri":          "Teslimat yeri nedir?",
    "yetki_kapsami":        "Vekilin yetki kapsamı nedir?",

    "sure":                 "Sözleşmenin süresi nedir? Belirli mi belirsiz mi?",
    "deneme_suresi":        "Deneme süresi uygulanacak mı? Kaç ay? (TBK max 2 ay)",
    "ihbar_suresi":         "Taraflarca kararlaştırılan ihbar süresi kaç haftadır?",
    "depozito":             "Depozito alınacak mı? Ne kadar?",
    "artis_orani":          "Yıllık kira artış oranı nasıl belirlenecek?",
    "odeme_plani":          "Ödeme planı nasıl olacak?",
    "odeme_yontemi":        "Ödeme yöntemi nedir?",
}


def get_question(field: str) -> str:
    return QUESTION_TEMPLATES.get(field, f"'{field}' bilgisi nedir?")
