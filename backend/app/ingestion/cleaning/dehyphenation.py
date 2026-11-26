"""Conservative line-break dehyphenation for Knovera."""

import re

# Naturally hyphenated prefixes that should retain hyphen even across line breaks
PRESERVE_HYPHEN_PREFIXES = {
    "self", "co", "re", "pre", "post", "well", "cross", "semi",
    "macro", "micro", "anti", "non", "multi", "quasi", "pseudo",
}

# Matches letters hyphenated at end of line: word-\nword
LINE_BREAK_HYPHEN_REGEX = re.compile(r"([a-zA-Z]{2,})-\n([a-zA-Z]{2,})")


def conservative_dehyphenate(text: str) -> tuple[str, int]:
    """Conservatively rejoins words split across line breaks by hyphens.

    Rules:
        - If the prefix is a known inherently hyphenated prefix (e.g. 'self', 'cross', 'multi'),
          rejoin with hyphen ('self-supervised').
        - Otherwise, rejoin into a single word ('learn' + 'ing' -> 'learning').
        - Preserves all inline hyphens, code identifiers, ranges (e.g. 2020-2026), and math minuses.
    """
    if not text or "-\n" not in text:
        return text, 0

    count = 0

    def replacer(match: re.Match) -> str:
        nonlocal count
        count += 1
        part1 = match.group(1)
        part2 = match.group(2)

        # Check if part1 is in inherently hyphenated prefixes
        if part1.lower() in PRESERVE_HYPHEN_PREFIXES:
            return f"{part1}-{part2}"

        # Otherwise rejoin without hyphen
        return f"{part1}{part2}"

    cleaned_text = LINE_BREAK_HYPHEN_REGEX.sub(replacer, text)
    return cleaned_text, count
