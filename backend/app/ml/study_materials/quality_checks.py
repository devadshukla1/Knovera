"""Quality Checks Orchestrator for Knovera Study Material Generation.

Provides high-level validation runners that produce structured StudyMaterialQualityReport
and filter out malformed or low-quality generation artifacts for:
- Revision Notes
- MCQs
- Fill-in-the-Blanks
- True/False Questions
- Flashcards
"""

from typing import Any, List, Optional, Tuple
from backend.app.ml.study_materials.schemas import (
    FillBlankExerciseCreate,
    FlashcardCreate,
    MCQQuestionCreate,
    QualityMetric,
    RevisionNoteCreate,
    StudyMaterialQualityReport,
    TrueFalseQuestionCreate,
)
from backend.app.ml.study_materials.validators import (
    FillBlankValidator,
    FlashcardValidator,
    MCQValidator,
    RevisionNoteValidator,
    TrueFalseValidator,
)


class StudyMaterialQualityValidator:
    """Orchestrates quality evaluation across all study material types."""

    @staticmethod
    def validate_revision_note(
        note: RevisionNoteCreate,
    ) -> Tuple[bool, StudyMaterialQualityReport]:
        passed, errors = RevisionNoteValidator.validate(note)
        checks = [
            QualityMetric(
                check_name="revision_note_structure",
                passed=passed,
                details="; ".join(errors) if errors else "Passed all structure checks",
            ),
            QualityMetric(
                check_name="sections_non_empty",
                passed=len(note.sections) > 0,
                details=f"Contains {len(note.sections)} sections",
            ),
        ]

        report = StudyMaterialQualityReport(
            total_requested=1,
            total_raw_generated=1,
            total_validated=1 if passed else 0,
            total_rejected=0 if passed else 1,
            validation_checks=checks,
            rejection_reasons=errors,
        )
        return passed, report

    @staticmethod
    def validate_revision_notes_batch(
        notes: Optional[List[RevisionNoteCreate]] = None,
        chunks: Any = None,
        items: Optional[List[RevisionNoteCreate]] = None,
    ) -> Tuple[List[RevisionNoteCreate], StudyMaterialQualityReport]:
        target = notes if notes is not None else (items or [])
        valid: List[RevisionNoteCreate] = []
        all_checks: List[QualityMetric] = []
        all_rejections: List[str] = []
        for n in target:
            passed, r = StudyMaterialQualityValidator.validate_revision_note(n)
            all_checks.extend(r.validation_checks)
            all_rejections.extend(r.rejection_reasons)
            if passed:
                valid.append(n)
        report = StudyMaterialQualityReport(
            total_requested=len(target),
            total_raw_generated=len(target),
            total_validated=len(valid),
            total_rejected=len(target) - len(valid),
            validation_checks=all_checks,
            rejection_reasons=all_rejections,
        )
        return valid, report

    @staticmethod
    def validate_mcq_batch(
        items: Optional[List[MCQQuestionCreate]] = None,
        total_requested: int = 1,
        questions: Optional[List[MCQQuestionCreate]] = None,
    ) -> Tuple[List[MCQQuestionCreate], StudyMaterialQualityReport]:
        target_items = items if items is not None else (questions or [])
        valid_items: List[MCQQuestionCreate] = []
        rejection_reasons: List[str] = []
        checks: List[QualityMetric] = []

        seen_stems = set()
        for idx, mcq in enumerate(target_items):
            norm_stem = " ".join(mcq.question_text.lower().split())
            if norm_stem in seen_stems:
                rejection_reasons.append(f"Question {idx + 1} is a duplicate stem: '{mcq.question_text}'")
                checks.append(
                    QualityMetric(
                        check_name=f"mcq_{idx + 1}_uniqueness",
                        passed=False,
                        details="Duplicate question text",
                    )
                )
                continue
            seen_stems.add(norm_stem)

            passed, errors = MCQValidator.validate(mcq)
            checks.append(
                QualityMetric(
                    check_name=f"mcq_{idx + 1}_integrity",
                    passed=passed,
                    details="; ".join(errors) if errors else "Valid 4-option single-correct MCQ",
                )
            )

            if passed:
                valid_items.append(mcq)
            else:
                rejection_reasons.extend([f"Question {idx + 1}: {e}" for e in errors])

        report = StudyMaterialQualityReport(
            total_requested=total_requested,
            total_raw_generated=len(target_items),
            total_validated=len(valid_items),
            total_rejected=len(target_items) - len(valid_items),
            validation_checks=checks,
            rejection_reasons=rejection_reasons,
        )
        return valid_items, report

    @staticmethod
    def validate_fill_blanks_batch(
        items: Optional[List[FillBlankExerciseCreate]] = None,
        total_requested: int = 1,
        exercises: Optional[List[FillBlankExerciseCreate]] = None,
    ) -> Tuple[List[FillBlankExerciseCreate], StudyMaterialQualityReport]:
        target_items = items if items is not None else (exercises or [])
        valid_items: List[FillBlankExerciseCreate] = []
        rejection_reasons: List[str] = []
        checks: List[QualityMetric] = []

        seen_sentences = set()
        for idx, item in enumerate(target_items):
            norm_sent = " ".join(item.original_sentence.lower().split())
            if norm_sent in seen_sentences:
                rejection_reasons.append(f"Exercise {idx + 1} duplicates original sentence")
                checks.append(
                    QualityMetric(
                        check_name=f"fill_blank_{idx + 1}_uniqueness",
                        passed=False,
                        details="Duplicate sentence",
                    )
                )
                continue
            seen_sentences.add(norm_sent)

            passed, errors, repaired = FillBlankValidator.validate_and_repair(item)
            checks.append(
                QualityMetric(
                    check_name=f"fill_blank_{idx + 1}_offset_and_reconstruction",
                    passed=passed,
                    details="; ".join(errors) if errors else "Verified character offsets and reconstruction",
                )
            )

            if passed:
                valid_items.append(repaired)
            else:
                rejection_reasons.extend([f"Exercise {idx + 1}: {e}" for e in errors])

        report = StudyMaterialQualityReport(
            total_requested=total_requested,
            total_raw_generated=len(target_items),
            total_validated=len(valid_items),
            total_rejected=len(target_items) - len(valid_items),
            validation_checks=checks,
            rejection_reasons=rejection_reasons,
        )
        return valid_items, report

    @staticmethod
    def validate_true_false_batch(
        items: Optional[List[TrueFalseQuestionCreate]] = None,
        total_requested: int = 1,
        questions: Optional[List[TrueFalseQuestionCreate]] = None,
    ) -> Tuple[List[TrueFalseQuestionCreate], StudyMaterialQualityReport]:
        target_items = items if items is not None else (questions or [])
        valid_items: List[TrueFalseQuestionCreate] = []
        rejection_reasons: List[str] = []
        checks: List[QualityMetric] = []

        seen_statements = set()
        for idx, item in enumerate(target_items):
            norm_stmt = " ".join(item.statement.lower().split())
            if norm_stmt in seen_statements:
                rejection_reasons.append(f"Question {idx + 1} duplicates statement")
                checks.append(
                    QualityMetric(
                        check_name=f"true_false_{idx + 1}_uniqueness",
                        passed=False,
                        details="Duplicate statement text",
                    )
                )
                continue
            seen_statements.add(norm_stmt)

            passed, errors = TrueFalseValidator.validate(item)
            checks.append(
                QualityMetric(
                    check_name=f"true_false_{idx + 1}_integrity",
                    passed=passed,
                    details="; ".join(errors) if errors else "Valid True/False question",
                )
            )

            if passed:
                valid_items.append(item)
            else:
                rejection_reasons.extend([f"Question {idx + 1}: {e}" for e in errors])

        report = StudyMaterialQualityReport(
            total_requested=total_requested,
            total_raw_generated=len(target_items),
            total_validated=len(valid_items),
            total_rejected=len(target_items) - len(valid_items),
            validation_checks=checks,
            rejection_reasons=rejection_reasons,
        )
        return valid_items, report

    @staticmethod
    def validate_flashcards_batch(
        items: Optional[List[FlashcardCreate]] = None,
        total_requested: int = 1,
        cards: Optional[List[FlashcardCreate]] = None,
    ) -> Tuple[List[FlashcardCreate], StudyMaterialQualityReport]:
        target_items = items if items is not None else (cards or [])
        valid_items: List[FlashcardCreate] = []
        rejection_reasons: List[str] = []
        checks: List[QualityMetric] = []

        seen_fronts = set()
        for idx, item in enumerate(target_items):
            norm_front = " ".join(item.front.lower().split())
            if norm_front in seen_fronts:
                rejection_reasons.append(f"Card {idx + 1} duplicates front prompt")
                checks.append(
                    QualityMetric(
                        check_name=f"flashcard_{idx + 1}_uniqueness",
                        passed=False,
                        details="Duplicate front prompt",
                    )
                )
                continue
            seen_fronts.add(norm_front)

            passed, errors = FlashcardValidator.validate(item)
            checks.append(
                QualityMetric(
                    check_name=f"flashcard_{idx + 1}_quality",
                    passed=passed,
                    details="; ".join(errors) if errors else "Valid high-yield flashcard",
                )
            )

            if passed:
                valid_items.append(item)
            else:
                rejection_reasons.extend([f"Card {idx + 1}: {e}" for e in errors])

        report = StudyMaterialQualityReport(
            total_requested=total_requested,
            total_raw_generated=len(target_items),
            total_validated=len(valid_items),
            total_rejected=len(target_items) - len(valid_items),
            validation_checks=checks,
            rejection_reasons=rejection_reasons,
        )
        return valid_items, report
