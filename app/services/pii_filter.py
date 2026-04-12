"""
PII sanitization for data sent to external LLMs.

Masks Turkish personally identifiable information patterns before
any data leaves the server boundary.
"""
import re
from typing import Dict, List

# Compiled at import time — not per-call — for performance.
_PATTERNS: List[tuple[re.Pattern, str]] = [
    # TC Kimlik Numarası: exactly 11 digits, first digit non-zero
    (re.compile(r'\b[1-9][0-9]{10}\b'), '[TC_KIMLIK]'),
    # Turkish IBAN: TR + 24 digits
    (re.compile(r'\bTR[0-9]{24}\b', re.IGNORECASE), '[IBAN]'),
    # Turkish phone numbers: +90 or 0 followed by 3-digit area/mobile code + 7 digits.
    # Lookbehind/ahead prevent matching digit substrings inside longer numbers (e.g. foreign IBANs).
    (re.compile(
        r'(?<!\d)(\+90|0)[\s\-]?(5[0-9]{2}|[2-4][0-9]{2})[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}(?!\d)'
    ), '[TELEFON]'),
    # Email addresses
    (re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'), '[EMAIL]'),
    # Passport numbers: 2 uppercase letters + exactly 7 digits
    (re.compile(r'\b[A-Z]{2}[0-9]{7}\b'), '[PASAPORT]'),
]


def sanitize_text(text: str) -> str:
    """Replace detected PII patterns with labeled placeholders."""
    for pattern, placeholder in _PATTERNS:
        text = pattern.sub(placeholder, text)
    return text


def sanitize_validation_errors(errors: List[Dict]) -> List[Dict]:
    """Return a new list of validation error dicts with the 'issue' field sanitized.

    Does not mutate the original list or its dicts.
    """
    result = []
    for err in errors:
        if 'issue' in err:
            result.append({**err, 'issue': sanitize_text(err['issue'])})
        else:
            result.append(err)
    return result
