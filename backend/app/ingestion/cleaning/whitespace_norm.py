"""Whitespace and newline normalization for Knovera."""

import re

# Multiple spaces or tabs on a single line
HORIZONTAL_WHITESPACE_REGEX = re.compile(r"[^\S\r\n]{2,}")
# 3 or more consecutive newlines
EXCESSIVE_NEWLINES_REGEX = re.compile(r"\n{3,}")


def normalize_whitespace(text: str) -> tuple[str, int]:
    """Normalizes line endings, collapses excessive blank lines, and trims trailing line spaces.

    Preserves:
        - Meaningful paragraph boundaries (\n\n)
        - Table pipe structures
        - Indentation where relevant
    """
    if not text:
        return "", 0

    original_len = len(text)

    # 1. Normalize line endings (\r\n and \r -> \n)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")

    # 2. Trim trailing spaces on each line
    lines = [line.rstrip() for line in normalized.split("\n")]
    normalized = "\n".join(lines)

    # 3. Collapse multiple spaces within a line (unless table line with pipes)
    clean_lines = []
    for line in normalized.split("\n"):
        if "|" in line:
            # Preserve table row spacing
            clean_lines.append(line)
        else:
            clean_lines.append(HORIZONTAL_WHITESPACE_REGEX.sub(" ", line))
    normalized = "\n".join(clean_lines)

    # 4. Collapse excessive vertical empty lines (> 2 newlines -> 2 newlines)
    normalized = EXCESSIVE_NEWLINES_REGEX.sub("\n\n", normalized)

    # 5. Trim leading/trailing document whitespace
    normalized = normalized.strip()

    changes = abs(original_len - len(normalized))
    return normalized, changes
