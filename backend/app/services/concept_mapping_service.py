"""Concept-Question Mapping Service for Knovera Learner Intelligence Foundation (Phase 9 C9.1).

Connects assessment questions (MCQ, True/False, FillBlank) with canonical KnowledgeNodes
from Phase 7 Knowledge Graph. Provides candidate generation, validation lifecycle, and provenance.
"""

from typing import Any, Dict, List, Optional, Tuple
import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.knowledge_mention import KnowledgeMention
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import QuestionConceptMapping
from backend.app.models.study_material import (
    FillBlankExercise,
    MCQQuestion,
    TrueFalseQuestion,
)
from backend.app.schemas.learner_intelligence import (
    ConceptQuestionsResponse,
    ConceptSummary,
    MappingMethod,
    MappingValidationStatus,
    QuestionConceptMappingCreate,
    QuestionConceptMappingResponse,
    QuestionConceptMappingUpdate,
    QuestionConceptsResponse,
)

logger = get_logger("knovera.services.concept_mapping")


class ConceptQuestionMappingService:
    """Service handling concept-to-question mappings, provenance, and candidate extraction."""

    def __init__(self, db: Session):
        self.db = db

    def resolve_question(
        self,
        workspace_id: uuid.UUID,
        question_id: uuid.UUID,
    ) -> Optional[Dict[str, Any]]:
        """Locates the question across MCQ, True/False, and FillBlank in the given workspace.

        Returns metadata dict or None if not found.
        """
        # 1. Check MCQ
        mcq = (
            self.db.query(MCQQuestion)
            .filter(
                MCQQuestion.id == question_id,
                MCQQuestion.workspace_id == workspace_id,
            )
            .first()
        )
        if mcq:
            chunk_ids = []
            if mcq.source_references:
                for ref in mcq.source_references:
                    cid = ref.get("chunk_id") if isinstance(ref, dict) else getattr(ref, "chunk_id", None)
                    if cid:
                        try:
                            chunk_ids.append(uuid.UUID(str(cid)))
                        except (ValueError, TypeError):
                            pass
            options_text = " ".join(opt.option_text for opt in mcq.options) if mcq.options else ""
            topic_tags_text = " ".join(mcq.topic_tags) if mcq.topic_tags else ""
            search_text = f"{mcq.question_text} {mcq.explanation} {options_text} {topic_tags_text}"

            return {
                "question_obj": mcq,
                "question_type": "mcq",
                "question_text": mcq.question_text,
                "difficulty": mcq.difficulty,
                "search_text": search_text,
                "chunk_ids": chunk_ids,
            }

        # 2. Check True/False
        tf = (
            self.db.query(TrueFalseQuestion)
            .filter(
                TrueFalseQuestion.id == question_id,
                TrueFalseQuestion.workspace_id == workspace_id,
            )
            .first()
        )
        if tf:
            chunk_ids = []
            if tf.chunk_id:
                chunk_ids.append(tf.chunk_id)
            if tf.source_references:
                for ref in tf.source_references:
                    cid = ref.get("chunk_id") if isinstance(ref, dict) else getattr(ref, "chunk_id", None)
                    if cid:
                        try:
                            chunk_ids.append(uuid.UUID(str(cid)))
                        except (ValueError, TypeError):
                            pass
            search_text = f"{tf.statement} {tf.explanation} {tf.topic or ''}"

            return {
                "question_obj": tf,
                "question_type": "true_false",
                "question_text": tf.statement,
                "difficulty": tf.difficulty,
                "search_text": search_text,
                "chunk_ids": chunk_ids,
            }

        # 3. Check FillBlank
        fb = (
            self.db.query(FillBlankExercise)
            .filter(
                FillBlankExercise.id == question_id,
                FillBlankExercise.workspace_id == workspace_id,
            )
            .first()
        )
        if fb:
            chunk_ids = []
            if fb.chunk_id:
                chunk_ids.append(fb.chunk_id)
            if fb.source_reference and isinstance(fb.source_reference, dict):
                cid = fb.source_reference.get("chunk_id")
                if cid:
                    try:
                        chunk_ids.append(uuid.UUID(str(cid)))
                    except (ValueError, TypeError):
                        pass
            search_text = f"{fb.sentence_with_blank} {fb.original_sentence} {fb.canonical_answer} {fb.hint or ''} {fb.explanation or ''}"

            return {
                "question_obj": fb,
                "question_type": "fill_blank",
                "question_text": fb.sentence_with_blank,
                "difficulty": fb.difficulty,
                "search_text": search_text,
                "chunk_ids": chunk_ids,
            }

        return None

    def create_mapping(
        self,
        workspace_id: uuid.UUID,
        question_id: uuid.UUID,
        data: QuestionConceptMappingCreate,
    ) -> QuestionConceptMapping:
        """Creates an explicit question-to-concept mapping with validation."""
        q_info = self.resolve_question(workspace_id, question_id)
        if not q_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question {question_id} not found in workspace {workspace_id}.",
            )

        # Check concept exists in workspace
        concept = (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.id == data.concept_id,
                KnowledgeNode.workspace_id == workspace_id,
            )
            .first()
        )
        if not concept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Canonical concept {data.concept_id} not found in workspace {workspace_id}.",
            )

        # Check unique constraint
        existing = (
            self.db.query(QuestionConceptMapping)
            .filter(
                QuestionConceptMapping.question_id == question_id,
                QuestionConceptMapping.concept_id == data.concept_id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Mapping between question {question_id} and concept {data.concept_id} already exists.",
            )

        mapping = QuestionConceptMapping(
            workspace_id=workspace_id,
            question_id=question_id,
            question_type=q_info["question_type"],
            concept_id=data.concept_id,
            mapping_method=data.mapping_method.value,
            confidence_score=data.confidence_score,
            validation_status=data.validation_status.value,
            evidence_excerpt=data.evidence_excerpt,
        )
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def get_question_concepts(
        self,
        workspace_id: uuid.UUID,
        question_id: uuid.UUID,
        status_filter: Optional[str] = None,
    ) -> QuestionConceptsResponse:
        """Returns all canonical concepts mapped to a specific question."""
        q_info = self.resolve_question(workspace_id, question_id)
        if not q_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question {question_id} not found in workspace {workspace_id}.",
            )

        query = (
            self.db.query(QuestionConceptMapping)
            .filter(
                QuestionConceptMapping.workspace_id == workspace_id,
                QuestionConceptMapping.question_id == question_id,
            )
        )
        if status_filter:
            query = query.filter(QuestionConceptMapping.validation_status == status_filter)

        mappings = query.all()

        results = []
        for m in mappings:
            concept_summary = None
            if m.concept:
                concept_summary = ConceptSummary(
                    id=m.concept.id,
                    name=m.concept.name,
                    normalized_name=m.concept.normalized_name,
                    node_type=m.concept.node_type,
                    category=m.concept.category,
                    description=m.concept.description,
                )

            results.append(
                QuestionConceptMappingResponse(
                    id=m.id,
                    workspace_id=m.workspace_id,
                    question_id=m.question_id,
                    question_type=m.question_type,
                    concept_id=m.concept_id,
                    concept=concept_summary,
                    mapping_method=MappingMethod(m.mapping_method),
                    confidence_score=m.confidence_score,
                    validation_status=MappingValidationStatus(m.validation_status),
                    evidence_excerpt=m.evidence_excerpt,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
            )

        return QuestionConceptsResponse(
            question_id=question_id,
            question_type=q_info["question_type"],
            total_mappings=len(results),
            mappings=results,
        )

    def get_concept_questions(
        self,
        workspace_id: uuid.UUID,
        concept_id: uuid.UUID,
        status_filter: Optional[str] = None,
    ) -> ConceptQuestionsResponse:
        """Returns all questions assessing a specific canonical concept."""
        concept = (
            self.db.query(KnowledgeNode)
            .filter(
                KnowledgeNode.id == concept_id,
                KnowledgeNode.workspace_id == workspace_id,
            )
            .first()
        )
        if not concept:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Canonical concept {concept_id} not found in workspace {workspace_id}.",
            )

        query = (
            self.db.query(QuestionConceptMapping)
            .filter(
                QuestionConceptMapping.workspace_id == workspace_id,
                QuestionConceptMapping.concept_id == concept_id,
            )
        )
        if status_filter:
            query = query.filter(QuestionConceptMapping.validation_status == status_filter)

        mappings = query.all()

        results = []
        for m in mappings:
            concept_summary = ConceptSummary(
                id=concept.id,
                name=concept.name,
                normalized_name=concept.normalized_name,
                node_type=concept.node_type,
                category=concept.category,
                description=concept.description,
            )
            results.append(
                QuestionConceptMappingResponse(
                    id=m.id,
                    workspace_id=m.workspace_id,
                    question_id=m.question_id,
                    question_type=m.question_type,
                    concept_id=m.concept_id,
                    concept=concept_summary,
                    mapping_method=MappingMethod(m.mapping_method),
                    confidence_score=m.confidence_score,
                    validation_status=MappingValidationStatus(m.validation_status),
                    evidence_excerpt=m.evidence_excerpt,
                    created_at=m.created_at,
                    updated_at=m.updated_at,
                )
            )

        return ConceptQuestionsResponse(
            concept_id=concept.id,
            concept_name=concept.name,
            total_questions=len(results),
            questions=results,
        )

    def generate_mappings_for_question(
        self,
        workspace_id: uuid.UUID,
        question_id: uuid.UUID,
        auto_validate: bool = False,
    ) -> List[QuestionConceptMapping]:
        """Automatically discovers candidate concept mappings for a question from workspace KnowledgeNodes."""
        q_info = self.resolve_question(workspace_id, question_id)
        if not q_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question {question_id} not found in workspace {workspace_id}.",
            )

        # Get existing mappings to avoid duplicate creation
        existing_concept_ids = set(
            row[0]
            for row in self.db.query(QuestionConceptMapping.concept_id)
            .filter(QuestionConceptMapping.question_id == question_id)
            .all()
        )

        nodes = (
            self.db.query(KnowledgeNode)
            .filter(KnowledgeNode.workspace_id == workspace_id)
            .all()
        )

        # Check source chunk mentions if available
        chunk_node_ids = set()
        if q_info["chunk_ids"]:
            mentions = (
                self.db.query(KnowledgeMention.node_id)
                .filter(KnowledgeMention.chunk_id.in_(q_info["chunk_ids"]))
                .all()
            )
            chunk_node_ids = set(row[0] for row in mentions)

        stem_lower = q_info["question_text"].lower()
        search_lower = q_info["search_text"].lower()

        created_mappings: List[QuestionConceptMapping] = []

        for node in nodes:
            if node.id in existing_concept_ids:
                continue

            node_name_lower = node.name.lower()
            node_norm_lower = node.normalized_name.lower()

            matched = False
            confidence = 0.5
            method = MappingMethod.DETERMINISTIC_EXTRACTION
            evidence = ""

            # 1. Direct name match in question stem
            if (len(node_name_lower) > 2 and node_name_lower in stem_lower) or (
                len(node_norm_lower) > 2 and node_norm_lower in stem_lower
            ):
                matched = True
                confidence = 0.95
                method = MappingMethod.DETERMINISTIC_EXTRACTION
                evidence = f"Concept '{node.name}' directly matched in question stem text."

            # 2. Match in explanation, options, or context
            elif (len(node_name_lower) > 2 and node_name_lower in search_lower) or (
                len(node_norm_lower) > 2 and node_norm_lower in search_lower
            ):
                matched = True
                confidence = 0.85
                method = MappingMethod.DETERMINISTIC_EXTRACTION
                evidence = f"Concept '{node.name}' identified in question options or explanation."

            # 3. Grounded in source chunk mention
            elif node.id in chunk_node_ids:
                matched = True
                confidence = 0.75
                method = MappingMethod.KNOWLEDGE_GRAPH
                evidence = f"Concept '{node.name}' linked via document chunk mention."

            # 4. Check aliases
            elif node.aliases:
                for alias in node.aliases:
                    if isinstance(alias, str) and len(alias) > 2 and alias.lower() in search_lower:
                        matched = True
                        confidence = 0.80
                        method = MappingMethod.KNOWLEDGE_GRAPH
                        evidence = f"Concept alias '{alias}' matched in question context."
                        break

            if matched:
                mapping = QuestionConceptMapping(
                    workspace_id=workspace_id,
                    question_id=question_id,
                    question_type=q_info["question_type"],
                    concept_id=node.id,
                    mapping_method=method.value,
                    confidence_score=confidence,
                    validation_status=MappingValidationStatus.VALIDATED.value
                    if auto_validate
                    else MappingValidationStatus.CANDIDATE.value,
                    evidence_excerpt=evidence,
                )
                self.db.add(mapping)
                created_mappings.append(mapping)
                existing_concept_ids.add(node.id)

        if created_mappings:
            self.db.commit()
            for m in created_mappings:
                self.db.refresh(m)

        return created_mappings

    def update_mapping(
        self,
        workspace_id: uuid.UUID,
        mapping_id: uuid.UUID,
        data: QuestionConceptMappingUpdate,
    ) -> QuestionConceptMapping:
        """Updates validation status, confidence score, or evidence excerpt."""
        mapping = (
            self.db.query(QuestionConceptMapping)
            .filter(
                QuestionConceptMapping.id == mapping_id,
                QuestionConceptMapping.workspace_id == workspace_id,
            )
            .first()
        )
        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mapping {mapping_id} not found in workspace {workspace_id}.",
            )

        if data.confidence_score is not None:
            mapping.confidence_score = data.confidence_score
        if data.validation_status is not None:
            mapping.validation_status = data.validation_status.value
        if data.evidence_excerpt is not None:
            mapping.evidence_excerpt = data.evidence_excerpt

        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def delete_mapping(
        self,
        workspace_id: uuid.UUID,
        mapping_id: uuid.UUID,
    ) -> bool:
        """Deletes a question-concept mapping."""
        mapping = (
            self.db.query(QuestionConceptMapping)
            .filter(
                QuestionConceptMapping.id == mapping_id,
                QuestionConceptMapping.workspace_id == workspace_id,
            )
            .first()
        )
        if not mapping:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mapping {mapping_id} not found in workspace {workspace_id}.",
            )

        self.db.delete(mapping)
        self.db.commit()
        return True
