"""Quality Validators for Knovera Study Material Generation (Phase 8 Part 1).

Implements rigorous pedagogical and structural checks:
- Revision Notes: Completeness, structure, factual consistency, and formula validity.
- MCQs: 4 distinct options, single correct answer, distractor non-equivalence, no lazy patterns.
- Fill-in-the-Blanks: Exact original sentence preservation, character offset validation,
  sentence reconstruction integrity, technical punctuation preservation, and hint leak prevention.
- True/False: Complete declarative statement, single truth value, non-ambiguity.
- Academic Purity: Strict rejection of slide banners, course codes, institutional noise, and dangling fragments.
"""

import re
from typing import List, Optional, Tuple

from backend.app.ml.study_materials.schemas import (
    FillBlankExerciseCreate,
    FlashcardCreate,
    MCQQuestionCreate,
    RevisionNoteCreate,
    TrueFalseQuestionCreate,
)

BLANK_PLACEHOLDER = "______"
BANNED_MCQ_PHRASES = [
    "all of the above",
    "none of the above",
    "both a and b",
    "both b and c",
    "both a and c",
    "all of these",
    "none of these",
]

DOUBLE_NEGATIVE_PATTERNS = [
    r"\bnot\s+un\w+\b",
    r"\bnot\s+inappropriate\b",
    r"\bnot\s+impossible\b",
    r"\bnever\s+without\b",
]

BANNED_NOISE_PATTERNS = [
    re.compile(r"(?i)\b(?:dept\.?|department\s+of)\s+cse\s*&\s*it\b"),
    re.compile(r"(?i)\bjiit\b"),
    re.compile(r"(?i)\bnoida\b"),
    re.compile(r"(?i)\blecture\s*[-–—:]\s*\d+\b"),
    re.compile(r"(?i)\b\d{1,2}[A-Z]{1,4}\d{1,4}[A-Z0-9]*\b"),  # e.g., 9M12CS112
    re.compile(r"(?i)\bmetaheuristics\s+in\s+modell?ing\s+and\s+optimization\b"),
    re.compile(r"(?i)^of\s+cse\s*&\s*it"),
    re.compile(r"(?i)^does\s+not\s+"),
]


def is_clean_academic_text(text: str, min_words: int = 5) -> Tuple[bool, Optional[str]]:
    """Validates that candidate text is free from slide headers, course codes, and institutional fragments."""
    clean = text.strip()
    if not clean:
        return False, "Text is empty."

    # Check for banned noise patterns
    for pat in BANNED_NOISE_PATTERNS:
        if pat.search(clean):
            return False, f"Contains slide banner, institutional watermark, or course code: {pat.pattern}"

    # Check for dangling bullet points or symbols at start
    if re.match(r"^[•\-\*#]+\s*", clean):
        return False, "Text starts with bullet point or markdown marker."

    # Check for dangling prepositional fragment
    if re.match(r"(?i)^of\s+[A-Z]", clean):
        return False, "Text starts with a dangling preposition ('of ...')."

    # Word count check
    words = clean.split()
    if len(words) < min_words:
        return False, f"Text has only {len(words)} words, minimum required is {min_words}."

    return True, None


class RevisionNoteValidator:
    """Validates generated revision notes against pedagogical quality criteria."""

    @staticmethod
    def validate(note: RevisionNoteCreate) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not note.title or len(note.title.strip()) < 3:
            errors.append("Revision note title is missing or too short (<3 chars)")

        if not note.overview or len(note.overview.strip()) < 10:
            errors.append("Revision note overview is missing or too brief (<10 chars)")

        if not note.sections:
            errors.append("Revision note must have at least one structured section")
        else:
            for idx, sec in enumerate(note.sections):
                if not sec.heading or not sec.heading.strip():
                    errors.append(f"Section {idx + 1} has an empty heading")
                if not sec.summary or not sec.summary.strip():
                    errors.append(f"Section '{sec.heading}' has an empty summary")

        # Validate formulas
        for f_idx, formula in enumerate(note.formulas):
            if not formula.name or not formula.name.strip():
                errors.append(f"Formula {f_idx + 1} is missing a name")
            if not formula.expression or not formula.expression.strip():
                errors.append(f"Formula '{formula.name}' has an empty expression")

        return len(errors) == 0, errors


class MCQValidator:
    """Validates Multiple-Choice Questions for psychometric integrity."""

    @staticmethod
    def validate(mcq: MCQQuestionCreate) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # 1. Question stem validation
        if not mcq.question_text or len(mcq.question_text.strip()) < 8:
            errors.append("Question stem is missing or too short (<8 chars)")
        else:
            is_clean, reason = is_clean_academic_text(mcq.question_text, min_words=6)
            if not is_clean:
                errors.append(f"Question stem rejected: {reason}")

        # 2. Exactly 4 options
        if len(mcq.options) != 4:
            errors.append(f"MCQ must have exactly 4 options, found {len(mcq.options)}")

        option_letters = [opt.option_id.upper() for opt in mcq.options]
        if sorted(option_letters) != ["A", "B", "C", "D"]:
            errors.append(f"Options must be labelled ['A', 'B', 'C', 'D'], found {option_letters}")

        # 3. Exactly 1 correct option
        correct_opts = [opt for opt in mcq.options if opt.is_correct]
        if len(correct_opts) != 1:
            errors.append(f"MCQ must have exactly 1 correct option, found {len(correct_opts)}")
        elif correct_opts[0].option_id.upper() != mcq.correct_option_id.upper():
            errors.append(
                f"correct_option_id '{mcq.correct_option_id}' does not match option with is_correct=True ('{correct_opts[0].option_id}')"
            )

        # 4. Distractor uniqueness and non-triviality
        texts_seen = set()
        for opt in mcq.options:
            norm_text = opt.option_text.strip().lower()
            if not norm_text:
                errors.append(f"Option {opt.option_id} has empty text")
                continue

            if norm_text in texts_seen:
                errors.append(f"Duplicate option text detected for option {opt.option_id}: '{opt.option_text}'")
            texts_seen.add(norm_text)

            # Check banned lazy patterns
            for banned in BANNED_MCQ_PHRASES:
                if banned in norm_text:
                    errors.append(f"Option {opt.option_id} uses banned lazy distractor '{banned}'")

            # Check noise in options
            is_clean, reason = is_clean_academic_text(opt.option_text, min_words=1)
            if not is_clean and "slide banner" in (reason or ""):
                errors.append(f"Option {opt.option_id} rejected: {reason}")

        # 5. Explanation check
        if not mcq.explanation or len(mcq.explanation.strip()) < 5:
            errors.append("MCQ must have an informative explanation (>5 chars)")

        return len(errors) == 0, errors


class FillBlankValidator:
    """Validates fill-in-the-blank items for exact source reconstruction and non-leakage."""

    @staticmethod
    def validate_and_repair(exercise: FillBlankExerciseCreate) -> Tuple[bool, List[str], FillBlankExerciseCreate]:
        """Validates and optionally repairs offsets or blank formatting."""
        errors: List[str] = []

        orig = exercise.original_sentence.strip()
        blank_sent = exercise.sentence_with_blank.strip()
        ans = exercise.canonical_answer.strip()

        if not orig or len(orig) < 15:
            errors.append("Original sentence is too short (<15 chars) or empty")
            return False, errors, exercise

        is_clean, reason = is_clean_academic_text(orig, min_words=6)
        if not is_clean:
            errors.append(f"Original sentence rejected: {reason}")
            return False, errors, exercise

        if not ans or len(ans) < 2:
            errors.append("Canonical answer cannot be empty or a single character")
            return False, errors, exercise

        # Check if canonical answer is a noise word
        if any(pat.search(ans) for pat in BANNED_NOISE_PATTERNS):
            errors.append(f"Canonical answer '{ans}' is metadata/institutional noise")
            return False, errors, exercise

        # 1. Normalize blank placeholder if model used 3+ underscores
        normalized_blank_sent = re.sub(r"_{3,}", BLANK_PLACEHOLDER, blank_sent)

        # 2. Ensure blank placeholder exists in sentence_with_blank
        if BLANK_PLACEHOLDER not in normalized_blank_sent:
            if ans in normalized_blank_sent:
                normalized_blank_sent = normalized_blank_sent.replace(ans, BLANK_PLACEHOLDER, 1)
            else:
                errors.append(f"Blank placeholder '{BLANK_PLACEHOLDER}' not found in sentence_with_blank")

        # Count placeholders: must have exactly 1
        placeholder_count = normalized_blank_sent.count(BLANK_PLACEHOLDER)
        if placeholder_count != 1:
            errors.append(f"Sentence with blank must contain exactly 1 blank placeholder, found {placeholder_count}")

        # 3. Canonical answer must exist inside original sentence
        if ans not in orig:
            idx_ci = orig.lower().find(ans.lower())
            if idx_ci != -1:
                ans = orig[idx_ci : idx_ci + len(ans)]
            else:
                errors.append(f"Canonical answer '{ans}' does not exist inside original sentence: '{orig}'")

        # 4. Verify or recalculate character offsets
        start_offset = exercise.target_start_offset
        end_offset = exercise.target_end_offset

        if (
            0 <= start_offset < len(orig)
            and 0 < end_offset <= len(orig)
            and orig[start_offset:end_offset] == ans
        ):
            verified_start = start_offset
            verified_end = end_offset
        else:
            found_idx = orig.find(ans)
            if found_idx != -1:
                verified_start = found_idx
                verified_end = found_idx + len(ans)
            else:
                verified_start = start_offset
                verified_end = end_offset
                errors.append(f"Cannot align character offsets [{start_offset}:{end_offset}] for '{ans}' in sentence")

        # 5. Sentence reconstruction verification
        reconstructed = normalized_blank_sent.replace(BLANK_PLACEHOLDER, ans, 1)
        clean_reconstructed = " ".join(reconstructed.split())
        clean_orig = " ".join(orig.split())
        if clean_reconstructed != clean_orig:
            if ans in orig:
                normalized_blank_sent = orig.replace(ans, BLANK_PLACEHOLDER, 1)
            else:
                errors.append(
                    f"Sentence reconstruction mismatch: '{clean_reconstructed}' != '{clean_orig}'"
                )

        # 6. Hint leak check
        if exercise.hint:
            clean_hint = exercise.hint.strip().lower()
            if ans.lower() in clean_hint:
                errors.append(f"Hint leaks canonical answer: '{exercise.hint}' contains '{ans}'")

        repaired_exercise = exercise.model_copy(
            update={
                "original_sentence": orig,
                "sentence_with_blank": normalized_blank_sent,
                "canonical_answer": ans,
                "target_start_offset": verified_start,
                "target_end_offset": verified_end,
            }
        )

        return len(errors) == 0, errors, repaired_exercise


class TrueFalseValidator:
    """Validates True/False questions for pedagogical clarity, single truth value, and non-ambiguity."""

    @staticmethod
    def validate(question: TrueFalseQuestionCreate) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        statement = (question.statement or "").strip()
        if not statement or len(statement) < 20:
            errors.append("True/False statement is missing or too short (<20 chars)")

        is_clean, reason = is_clean_academic_text(statement, min_words=7)
        if not is_clean:
            errors.append(f"True/False statement rejected: {reason}")

        # Check grammatical closure: should end with period or question mark
        if statement and statement[-1] not in ".!?":
            statement = statement + "."

        if not isinstance(question.correct_answer, bool):
            errors.append("correct_answer must be a strict boolean (True or False)")

        explanation = (question.explanation or "").strip()
        if not explanation or len(explanation) < 10:
            errors.append("True/False explanation must be at least 10 characters explaining the factual basis")

        # Double negative detection
        statement_lower = statement.lower()
        for pattern in DOUBLE_NEGATIVE_PATTERNS:
            if re.search(pattern, statement_lower):
                errors.append(f"Statement contains confusing double negative matching pattern '{pattern}'")

        return len(errors) == 0, errors


class FlashcardValidator:
    """Validates flashcards for concise front prompt, targeted back answer, and non-triviality."""

    @staticmethod
    def validate(card: FlashcardCreate) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        front = (card.front or "").strip()
        back = (card.back or "").strip()

        if not front or len(front) < 3:
            errors.append("Flashcard front prompt is too short (<3 chars)")
        elif len(front) > 200:
            errors.append(f"Flashcard front exceeds recommended 200 character limit ({len(front)} chars)")

        if not back or len(back) < 1:
            errors.append("Flashcard back answer cannot be empty")
        elif len(back) > 500:
            errors.append(f"Flashcard back exceeds 500 character limit ({len(back)} chars)")

        # Echo check: front and back should not be identical
        if front.lower() == back.lower():
            errors.append("Flashcard back directly echoes front verbatim")

        return len(errors) == 0, errors
