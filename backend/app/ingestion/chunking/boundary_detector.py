"""Sentence boundary detection and segmentation for Knovera."""

import re
from typing import List

# Common abbreviations that should NOT trigger a sentence split
ABBREVIATIONS = {
    "e.g.", "i.e.", "et al.", "etc.", "vs.", "fig.", "figs.", "al.",
    "dr.", "mr.", "mrs.", "ms.", "prof.", "sr.", "jr.", "approx.",
    "dept.", "univ.", "vol.", "no.", "p.", "pp.", "ed.", "eds.",
}

# Regex to find candidate sentence split positions: period, exclamation, question mark followed by space + uppercase/quote
CANDIDATE_SPLIT_REGEX = re.compile(r"([.!?]+)([\s]+)(?=[A-Z0-9\"'(\[])")


class SentenceBoundaryDetector:
    """Robust sentence boundary segmentation preserving technical notation and abbreviations."""

    def split_sentences(self, paragraph: str) -> List[str]:
        """Splits a paragraph into coherent sentences without breaking abbreviations, decimals, or URLs."""
        if not paragraph or not paragraph.strip():
            return []

        clean_p = paragraph.strip()

        # If short or no punctuation, return as single sentence
        if len(clean_p) < 40 or not any(p in clean_p for p in ".!?"):
            return [clean_p]

        # Scan and validate split positions
        sentences: List[str] = []
        last_idx = 0

        for match in CANDIDATE_SPLIT_REGEX.finditer(clean_p):
            punct_end = match.end(1)
            split_point = match.end()

            candidate_before = clean_p[last_idx:punct_end].strip()
            # Get last word before punctuation
            words = candidate_before.split()
            last_word = words[-1].lower() if words else ""
            clean_word = last_word.strip("()[]\"'")
            if not clean_word.endswith(".") and candidate_before.endswith("."):
                clean_word = f"{clean_word}."

            # Check if last word is a known abbreviation (e.g. "e.g.", "dr.", "et al.")
            if clean_word in ABBREVIATIONS or last_word in ABBREVIATIONS:
                continue

            # Check if this looks like a decimal number, e.g. "3." in "3.14"
            if len(candidate_before) >= 2 and candidate_before[-2].isdigit():
                # Check character right after punctuation
                after_char = clean_p[punct_end:punct_end + 1]
                if after_char.isdigit():
                    continue

            # Check if this looks like a single-letter initial (e.g. "J.")
            if len(last_word) == 2 and last_word[0].isalpha() and last_word[1] == ".":
                continue

            # Check if inside a URL or email
            if "://" in candidate_before and " " not in candidate_before[candidate_before.rfind("://"):]:
                continue

            # Valid boundary found
            sentence = clean_p[last_idx:split_point].strip()
            if sentence:
                sentences.append(sentence)
            last_idx = split_point

        remainder = clean_p[last_idx:].strip()
        if remainder:
            sentences.append(remainder)

        return sentences if sentences else [clean_p]
