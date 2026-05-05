CONTRACT_SCHEMAS = {
    "borc_sozlesmesi": {
        "required_spacy_labels": ["PERSON", "MONEY", "DATE"],
        "required_fields": [
            "taraf_alacakli",
            "taraf_borclu",
            "borc_tutari",
            "baslangic_tarihi",
        ],
        "optional_fields": [
            "faiz_orani",
            "vade",
            "odeme_yontemi",
            "odeme_plani",
            "temerrut_faizi",
            "kefalet",
            "ceza_kosulu",
            "yetkili_mahkeme",
        ]
    },
    "is_sozlesmesi": {
        "required_spacy_labels": ["PERSON", "ORG", "MONEY", "DATE"],
        "required_fields": [
            "taraf_isci",
            "taraf_isveren",
            "ucret",
            "baslangic_tarihi",
            "is_tanimi",
            "calisma_yeri",
        ],
        "optional_fields": [
            "sure",
            "deneme_suresi",
            "ihbar_suresi",
            "bitis_tarihi",
        ]
    },
    "kira_sozlesmesi": {
        "required_spacy_labels": ["PERSON", "MONEY", "DATE", "LOC"],
        "required_fields": [
            "taraf_kiraci",
            "taraf_kiraya_veren",
            "kira_bedeli",
            "baslangic_tarihi",
            "kiralanan_adres",
        ],
        "optional_fields": [
            "sure",
            "depozito",
            "artis_orani",
            "bitis_tarihi",
        ]
    },
    "satis_sozlesmesi": {
        "required_spacy_labels": ["PERSON", "ORG", "MONEY", "DATE"],
        "required_fields": [
            "taraf_alici",
            "taraf_satici",
            "satis_bedeli",
            "teslim_tarihi",
        ],
        "optional_fields": [
            "teslim_yeri",
            "odeme_plani",
        ]
    },
    "hizmet_sozlesmesi": {
        "required_spacy_labels": ["PERSON", "ORG", "MONEY", "DATE"],
        "required_fields": [
            "taraf_1",
            "taraf_2",
            "hizmet_bedeli",
            "baslangic_tarihi",
            "hizmet_tanimi",
        ],
        "optional_fields": [
            "sure",
            "bitis_tarihi",
            "odeme_yontemi",
        ]
    },
    "vekaletname": {
        "required_spacy_labels": ["PERSON", "DATE"],
        "required_fields": [
            "muvekkil",
            "vekil",
            "baslangic_tarihi",
        ],
        "optional_fields": [
            "sure",
            "yetki_kapsami",
        ]
    },
    "taahhutname": {
        "required_spacy_labels": ["PERSON", "DATE"],
        "required_fields": [
            "taraf_1",
            "baslangic_tarihi",
        ],
        "optional_fields": [
            "taraf_2",
            "sure",
        ]
    },
    "kefalet_sozlesmesi": {
        "required_spacy_labels": ["PERSON", "MONEY", "DATE"],
        "required_fields": [
            "kefil",
            "alacakli",
            "kefalet_miktari",
            "baslangic_tarihi",
        ],
        "optional_fields": [
            "sure",
        ]
    },
}

SUPPORTED_CONTRACT_TYPES = list(CONTRACT_SCHEMAS.keys())
