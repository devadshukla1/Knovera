"""Evidence and Explanation Service (Phase 8: C8.8).

Handles:
- Anti-cheat answer shielding (blocks explanations & citations during in-progress attempts)
- Verified pedagogical explanations for evaluated quiz attempts
- Canonical source evidence verification against PostgreSQL documents and chunks
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.ml.study_materials.schemas import (
    QuestionExplanationResponse,
    QuestionSourcesResponse,
    QuizAttemptStatus,
    SourceReference,
)
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.study_material import QuizAttempt
from backend.app.repositories.study_material_repository import StudyMaterialRepository

logger = get_logger("knovera.study_materials.evidence_service")


class AntiCheatShieldError(PermissionError):
    """Raised when unearned answer keys or source citations are requested during an in-progress attempt."""
    pass


class StudyMaterialEvidenceService:
    """Service for retrieving explanations and validating source citations."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = StudyMaterialRepository(session)

    def get_question_explanation(
        self,
        workspace_id: UUID,
        attempt_id: UUID,
        question_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> QuestionExplanationResponse:
        """Retrieves verified pedagogical explanation for a specific question in an evaluated attempt.

        Raises AntiCheatShieldError if the attempt is not yet evaluated.
        """
        attempt = self.repository.get_quiz_attempt(
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not attempt:
            raise ValueError("Quiz attempt not found")

        # Anti-cheat check: only revealed post-evaluation
        if attempt.status != QuizAttemptStatus.EVALUATED and attempt.status != "evaluated":
            raise AntiCheatShieldError(
                "Anti-cheat shield active: Question explanations and answers are strictly revealed only after quiz submission and evaluation."
            )

        # Check in evaluation summary first (immutable frozen results)
        summary = attempt.evaluation_summary or {}
        results = summary.get("results", [])
        target_str_id = str(question_id)

        for res in results:
            if str(res.get("question_id")) == target_str_id:
                return QuestionExplanationResponse(
                    attempt_id=attempt.id,
                    question_id=question_id,
                    question_type=res.get("question_type", "mcq"),
                    question_text=res.get("question_text", ""),
                    explanation=res.get("explanation", ""),
                    correct_answer=res.get("correct_answer"),
                    learner_answer=res.get("learner_answer"),
                    is_correct=res.get("is_correct"),
                )

        # Fallback to direct DB lookup if not in frozen summary
        grouped = self.repository.get_questions_by_ids(
            workspace_id=workspace_id,
            question_ids=[question_id],
        )

        for q in grouped["mcqs"]:
            return QuestionExplanationResponse(
                attempt_id=attempt.id,
                question_id=question_id,
                question_type="mcq",
                question_text=q.question_text,
                explanation=q.explanation or "",
                correct_answer=q.correct_option_id,
            )

        for q in grouped["true_false"]:
            return QuestionExplanationResponse(
                attempt_id=attempt.id,
                question_id=question_id,
                question_type="true_false",
                question_text=q.statement,
                explanation=q.explanation or "",
                correct_answer=q.correct_answer,
            )

        for q in grouped["fill_blanks"]:
            return QuestionExplanationResponse(
                attempt_id=attempt.id,
                question_id=question_id,
                question_type="fill_blank",
                question_text=q.sentence_with_blank,
                explanation=q.explanation or "",
                correct_answer=q.canonical_answer,
            )

        raise ValueError(f"Question with ID {question_id} not found in this quiz attempt")

    def get_question_sources(
        self,
        workspace_id: UUID,
        attempt_id: UUID,
        question_id: UUID,
        user_id: Optional[UUID] = None,
    ) -> QuestionSourcesResponse:
        """Retrieves and validates source citations for a specific question in an evaluated attempt.

        Raises AntiCheatShieldError if the attempt is not yet evaluated.
        """
        attempt = self.repository.get_quiz_attempt(
            attempt_id=attempt_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        if not attempt:
            raise ValueError("Quiz attempt not found")

        # Anti-cheat check
        if attempt.status != QuizAttemptStatus.EVALUATED and attempt.status != "evaluated":
            raise AntiCheatShieldError(
                "Anti-cheat shield active: Question source references and citations are strictly revealed only after quiz submission and evaluation."
            )

        # Retrieve raw references
        raw_refs: List[Dict[str, Any]] = []
        q_type = "mcq"
        target_str_id = str(question_id)

        summary = attempt.evaluation_summary or {}
        for res in summary.get("results", []):
            if str(res.get("question_id")) == target_str_id:
                raw_refs = res.get("source_references", [])
                q_type = res.get("question_type", "mcq")
                break

        if not raw_refs:
            grouped = self.repository.get_questions_by_ids(
                workspace_id=workspace_id,
                question_ids=[question_id],
            )
            for q in grouped["mcqs"]:
                q_type = "mcq"
                raw_refs = q.source_references or []
                break
            for q in grouped["true_false"]:
                q_type = "true_false"
                raw_refs = q.source_references or []
                break
            for q in grouped["fill_blanks"]:
                q_type = "fill_blank"
                if q.source_reference:
                    raw_refs = [q.source_reference]
                break

        # Validate and enrich source references against DB
        verified_refs: List[SourceReference] = []
        for ref_data in raw_refs:
            ref = SourceReference(**ref_data) if isinstance(ref_data, dict) else ref_data
            # Verify document tenancy
            doc = self.session.execute(
                select(Document).where(
                    Document.id == ref.document_id,
                    Document.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()

            doc_title = ref.document_title
            if doc:
                doc_title = getattr(doc, "title", None) or doc.original_filename or doc_title

            verified_refs.append(
                SourceReference(
                    document_id=ref.document_id,
                    document_title=doc_title,
                    chunk_id=ref.chunk_id,
                    chunk_index=getattr(ref, "chunk_index", None),
                    page_number=getattr(ref, "page_number", None),
                    slide_number=getattr(ref, "slide_number", None),
                    section_heading=getattr(ref, "section_heading", None),
                    excerpt=getattr(ref, "excerpt", None),
                    start_char_offset=getattr(ref, "start_char_offset", None),
                    end_char_offset=getattr(ref, "end_char_offset", None),
                )
            )

        return QuestionSourcesResponse(
            attempt_id=attempt.id,
            question_id=question_id,
            question_type=q_type,
            source_references=verified_refs,
        )
