import pytest
from app.services.pii_filter import sanitize_text, sanitize_validation_errors


# --- sanitize_text ---

def test_tc_kimlik_redacted():
    assert sanitize_text("Kimlik: 12345678901") == "Kimlik: [TC_KIMLIK]"

def test_tc_kimlik_zero_start_not_redacted():
    # TC Kimlik never starts with 0
    assert sanitize_text("01234567890") == "01234567890"

def test_tc_kimlik_ten_digits_not_redacted():
    assert sanitize_text("1234567890") == "1234567890"

def test_iban_redacted():
    assert sanitize_text("IBAN: TR330006100519786457841326") == "IBAN: [IBAN]"

def test_iban_lowercase_redacted():
    assert sanitize_text("tr330006100519786457841326") == "[IBAN]"

def test_foreign_iban_not_redacted():
    # Only Turkish IBANs should be redacted
    assert sanitize_text("DE89370400440532013000") == "DE89370400440532013000"

def test_phone_international_redacted():
    result = sanitize_text("+90 532 123 45 67")
    assert result == "[TELEFON]"

def test_phone_local_redacted():
    assert sanitize_text("05321234567") == "[TELEFON]"

def test_phone_with_dashes_redacted():
    assert sanitize_text("0532-123-45-67") == "[TELEFON]"

def test_email_redacted():
    assert sanitize_text("ahmet@example.com") == "[EMAIL]"

def test_email_in_sentence_redacted():
    result = sanitize_text("Lütfen ahmet@example.com adresine gönderin.")
    assert "[EMAIL]" in result
    assert "ahmet@example.com" not in result

def test_passport_redacted():
    assert sanitize_text("Pasaport: AB1234567") == "Pasaport: [PASAPORT]"

def test_passport_too_short_not_redacted():
    assert sanitize_text("AB123456") == "AB123456"

def test_no_false_positive_cardinal_duration():
    # The most common validation error value — a short duration — must pass through
    text = "Deneme süresi 3 ay olarak belirlenmiş. TBK m.393 uyarınca maksimum 2 aydır."
    assert sanitize_text(text) == text

def test_no_false_positive_short_cardinal():
    assert sanitize_text("1 hafta ihbar süresi") == "1 hafta ihbar süresi"

def test_idempotent():
    text = "Kimlik: 12345678901"
    once = sanitize_text(text)
    twice = sanitize_text(once)
    assert once == twice


# --- sanitize_validation_errors ---

def test_sanitize_validation_errors_sanitizes_issue():
    errors = [{"field": "tc", "issue": "TC: 12345678901 geçersiz.", "tbk_limit": "TBK m.1"}]
    result = sanitize_validation_errors(errors)
    assert result[0]["issue"] == "TC: [TC_KIMLIK] geçersiz."

def test_sanitize_validation_errors_no_mutation():
    errors = [{"field": "tc", "issue": "TC: 12345678901"}]
    original_issue = errors[0]["issue"]
    sanitize_validation_errors(errors)
    assert errors[0]["issue"] == original_issue

def test_sanitize_validation_errors_missing_issue_key():
    errors = [{"field": "deneme_suresi", "tbk_limit": "TBK m.393"}]
    result = sanitize_validation_errors(errors)
    assert result == errors

def test_sanitize_validation_errors_preserves_other_fields():
    errors = [{"field": "ihbar_suresi", "issue": "1 hafta belirlenmiş.", "tbk_limit": "TBK m.432"}]
    result = sanitize_validation_errors(errors)
    assert result[0]["field"] == "ihbar_suresi"
    assert result[0]["tbk_limit"] == "TBK m.432"
    assert result[0]["issue"] == "1 hafta belirlenmiş."

def test_sanitize_validation_errors_empty_list():
    assert sanitize_validation_errors([]) == []
