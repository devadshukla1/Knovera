"""Unicode normalization and control character sanitization for Knovera."""

import re
import unicodedata

# Dangerous control characters: NUL and ascii 0-8, 11-12, 14-31, 127 (excluding \t (9) and \n (10))
CONTROL_CHAR_REGEX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Zero-width spaces and BOM markers that disrupt text tokenization without semantic value
ZERO_WIDTH_REGEX = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\ufeff]")


def normalize_unicode(text: str) -> tuple[str, int, int]:
    """Normalizes text to Unicode NFC and removes invalid control/invisible characters.

    Preserves:
        - Accents and diacritics (e.g. é, ü, ç, ñ)
        - Mathematical symbols (e.g. ∑, ∫, ≤, ≥, ≠, ±, √, ∞)
        - Greek letters (e.g. α, β, γ, π, θ)
        - Currency symbols ($, €, £, ¥, ₹)
        - Technical and code punctuation
        - Newlines (\n) and tabs (\t)

    Returns:
        tuple of (normalized_text, removed_control_count, unicode_changes_count)
    """
    if not text:
        return "", 0, 0

    # 1. Count control characters
    control_matches = len(CONTROL_CHAR_REGEX.findall(text))
    # Remove control characters
    clean_text = CONTROL_CHAR_REGEX.sub("", text)

    # 2. Remove zero-width formatting characters
    clean_text = ZERO_WIDTH_REGEX.sub("", clean_text)

    # 3. Unicode NFC Normalization
    nfc_text = unicodedata.normalize("NFC", clean_text)

    # Track if unicode changed
    unicode_changes = 1 if nfc_text != clean_text else 0

    return nfc_text, control_matches, unicode_changes
