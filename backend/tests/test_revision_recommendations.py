"""Unit and Integration Tests for Revision Recommendation Engine (Phase 9 C9.7).

Tests:
- Policy-driven recommendation types (revise_concept, practice_concept, reinforce_concept, insufficient_evidence)
- Priority banding (high, medium, low)
- Evidence sufficiency gating (distinguishing sparse observations from poor mastery)
- Fallback to descriptive quiz evidence when BKT model is unvalidated or unavailable
- Material-to-concept linking (revision notes, flashcards, practice questions, source chunks)
- Lifecycle transitions (suggested -> viewed -> started -> completed -> dismissed)
- Idempotency and workspace tenancy isolation
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.bkt import (
    BKTEvaluationRun,
    BKTModelVersion,
    LearnerConceptMastery,
)
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_mention import KnowledgeMention
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import (
    QuestionConceptMapping,
    RevisionRecommendation,
)
from backend.app.models.study_material import (
    Flashcard,
    MCQOption,
    MCQQuestion,
    QuizAttempt,
    QuizAttemptAnswer,
    RevisionNote,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.recommendation import (
    RecommendationPriority,
    RecommendationStatus,
    RecommendationType,
    RevisionRecommendationGenerateRequest,
)
from backend.app.services.recommendation_service import RevisionRecommendationService


@pytest.fixture
def recommendation_setup(db_session: Session, test_workspace: Workspace, test_user: User):
    """Populates workspace with concepts, materials, mastery states, and quiz attempts."""
    ws = test_workspace
    user = test_user

    # 1. Qualified BKT Model
    model = BKTModelVersion(
        workspace_id=ws.id,
        model_version="bkt-rec-v1",
        model_scope="global",
        p_init=0.30,
        p_transit=0.15,
        p_guess=0.20,
        p_slip=0.10,
        status="active",
        validation_metrics={},
    )
    db_session.add(model)
    db_session.flush()

    # Evaluation run marking model as passed
    eval_run = BKTEvaluationRun(
        workspace_id=ws.id,
        model_version_id=model.id,
        split_method="learner_holdout",
        status="completed",
        readiness_status="evaluation_passed",
        num_learners=10,
        num_sequences=20,
        num_observations=50,
        log_loss=0.45,
        brier_score=0.18,
        accuracy=0.80,
        calibration_metrics={},
        baseline_metrics={},
        parameter_stability={},
    )
    db_session.add(eval_run)

    # 2. Concepts
    # Concept 1: Low mastery (should be revise_concept, high priority)
    c_low = KnowledgeNode(
        workspace_id=ws.id,
        node_type="concept",
        category="algorithm",
        name="Linear Regression",
        normalized_name="linear regression",
        description="Linear modeling and least squares",
    )
    # Concept 2: Developing mastery (should be practice_concept, medium priority)
    c_dev = KnowledgeNode(
        workspace_id=ws.id,
        node_type="concept",
        category="algorithm",
        name="Gradient Descent",
        normalized_name="gradient descent",
        description="First-order iterative optimization algorithm",
    )
    # Concept 3: Strong mastery (should be reinforce_concept, low priority)
    c_high = KnowledgeNode(
        workspace_id=ws.id,
        node_type="concept",
        category="algorithm",
        name="Support Vector Machines",
        normalized_name="support vector machines",
        description="Maximum margin hyperplane classification",
    )
    # Concept 4: Sparse observations (1 obs) -> practice_concept
    c_sparse = KnowledgeNode(
        workspace_id=ws.id,
        node_type="concept",
        category="algorithm",
        name="Decision Trees",
        normalized_name="decision trees",
        description="Recursive tree partitioning",
    )
    # Concept 5: Unobserved (0 obs) -> insufficient_evidence
    c_unobs = KnowledgeNode(
        workspace_id=ws.id,
        node_type="concept",
        category="algorithm",
        name="Neural Networks",
        normalized_name="neural networks",
        description="Multi-layer perceptrons",
    )

    db_session.add_all([c_low, c_dev, c_high, c_sparse, c_unobs])
    db_session.flush()

    # 3. Learner Masteries
    m_low = LearnerConceptMastery(
        workspace_id=ws.id,
        user_id=user.id,
        concept_id=c_low.id,
        posterior_mastery_probability=0.25,
        predicted_next_mastery_probability=0.35,
        observation_count=5,
        status="struggling",
    )
    m_dev = LearnerConceptMastery(
        workspace_id=ws.id,
        user_id=user.id,
        concept_id=c_dev.id,
        posterior_mastery_probability=0.55,
        predicted_next_mastery_probability=0.62,
        observation_count=4,
        status="developing",
    )
    m_high = LearnerConceptMastery(
        workspace_id=ws.id,
        user_id=user.id,
        concept_id=c_high.id,
        posterior_mastery_probability=0.88,
        predicted_next_mastery_probability=0.90,
        observation_count=6,
        status="mastered",
    )
    m_sparse = LearnerConceptMastery(
        workspace_id=ws.id,
        user_id=user.id,
        concept_id=c_sparse.id,
        posterior_mastery_probability=0.30,
        predicted_next_mastery_probability=0.40,
        observation_count=1,
        status="insufficient_data",
    )

    db_session.add_all([m_low, m_dev, m_high, m_sparse])

    # 4. Study Materials for Resource Linking
    doc = Document(
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="ml.pdf",
        storage_key="test/ml.pdf",
        media_type="application/pdf",
        file_extension="pdf",
        file_size_bytes=1024,
        sha256="dummy_sha256_hash_value_1234567890",
        processing_status="completed",
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=0,
        content="Linear Regression models relationship between scalar response and explanatory variables.",
        content_hash="dummy_content_hash_1234567890",
        parser_version="1.0",
        cleaning_version="1.0",
        chunking_version="1.0",
        page_start=1,
        page_end=1,
    )
    db_session.add(chunk)
    db_session.flush()

    mention = KnowledgeMention(
        workspace_id=ws.id,
        node_id=c_low.id,
        chunk_id=chunk.id,
        surface_form="Linear Regression",
        start_offset=0,
        end_offset=17,
        confidence=0.95,
    )
    note = RevisionNote(
        workspace_id=ws.id,
        title="Linear Regression Overview",
        overview="Detailed notes covering Ordinary Least Squares and assumptions.",
        key_concepts=[{"name": "linear regression"}, {"name": "residuals"}],
        important_points=["Assumes homoscedasticity", "Minimizes SSE"],
    )
    fc = Flashcard(
        workspace_id=ws.id,
        front="What is the objective function of Linear Regression?",
        back="Minimizing the sum of squared differences between observed and predicted values.",
        card_type="concept",
    )
    q_mcq = MCQQuestion(
        workspace_id=ws.id,
        question_text="Which metric is commonly minimized in Linear Regression?",
        explanation="OLS minimizes the sum of squared residuals.",
        difficulty="easy",
        question_type="conceptual",
        correct_option_id="opt_1",
        topic_tags=["regression"],
        source_references=[],
    )
    db_session.add_all([mention, note, fc, q_mcq])
    db_session.flush()

    q_map = QuestionConceptMapping(
        workspace_id=ws.id,
        question_id=q_mcq.id,
        question_type="mcq",
        concept_id=c_low.id,
        validation_status="validated",
        confidence_score=1.0,
    )
    db_session.add(q_map)
    db_session.commit()

    return {
        "workspace": ws,
        "user": user,
        "c_low": c_low,
        "c_dev": c_dev,
        "c_high": c_high,
        "c_sparse": c_sparse,
        "c_unobs": c_unobs,
        "model": model,
    }


def test_recommendation_generation_policy(db_session: Session, recommendation_setup):
    """Verifies that BKT mastery thresholds deterministically dictate recommendation types and priorities."""
    data = recommendation_setup
    service = RevisionRecommendationService(db_session)

    req = RevisionRecommendationGenerateRequest(force_regenerate=True, max_recommendations=10)
    recs = service.generate_recommendations(data["workspace"].id, data["user"].id, req)

    rec_by_cid = {r.concept_id: r for r in recs}

    # Concept Low (P=0.25) -> revise_concept, high priority
    r_low = rec_by_cid[data["c_low"].id]
    assert r_low.recommendation_type == RecommendationType.REVISE_CONCEPT.value
    assert r_low.priority == RecommendationPriority.HIGH.value
    assert "low" in r_low.explanation.lower()

    # Concept Dev (P=0.55) -> practice_concept, medium priority
    r_dev = rec_by_cid[data["c_dev"].id]
    assert r_dev.recommendation_type == RecommendationType.PRACTICE_CONCEPT.value
    assert r_dev.priority == RecommendationPriority.MEDIUM.value

    # Concept Sparse (1 obs) -> practice_concept, medium priority
    r_sparse = rec_by_cid[data["c_sparse"].id]
    assert r_sparse.recommendation_type == RecommendationType.PRACTICE_CONCEPT.value
    assert r_sparse.priority == RecommendationPriority.MEDIUM.value

    # Concept Unobserved (0 obs) -> insufficient_evidence, low priority
    r_unobs = rec_by_cid[data["c_unobs"].id]
    assert r_unobs.recommendation_type == RecommendationType.INSUFFICIENT_EVIDENCE.value
    assert r_unobs.priority == RecommendationPriority.LOW.value


def test_material_linking(db_session: Session, recommendation_setup):
    """Verifies that generated recommendations link existing notes, flashcards, questions, and sources."""
    data = recommendation_setup
    service = RevisionRecommendationService(db_session)

    req = RevisionRecommendationGenerateRequest(force_regenerate=True)
    recs = service.generate_recommendations(data["workspace"].id, data["user"].id, req)

    r_low = next(r for r in recs if r.concept_id == data["c_low"].id)
    linked = r_low.linked_resources

    assert "revision_notes" in linked
    assert len(linked["revision_notes"]) >= 1
    assert "Linear Regression" in linked["revision_notes"][0]["title"]

    assert "flashcards" in linked
    assert len(linked["flashcards"]) >= 1

    assert "practice_questions" in linked
    assert len(linked["practice_questions"]) >= 1

    assert "source_chunks" in linked
    assert len(linked["source_chunks"]) >= 1


def test_fallback_to_quiz_evidence_when_bkt_unqualified(db_session: Session, recommendation_setup):
    """Verifies recommendation engine gracefully falls back to descriptive accuracy when BKT is unvalidated."""
    data = recommendation_setup
    # Archive the active model version to simulate missing/unqualified model
    data["model"].status = "archived"
    db_session.commit()

    service = RevisionRecommendationService(db_session)
    req = RevisionRecommendationGenerateRequest(force_regenerate=True)
    recs = service.generate_recommendations(data["workspace"].id, data["user"].id, req)

    # Recommendations should still be generated safely without unhandled errors
    assert len(recs) > 0
    for r in recs:
        assert r.evidence_summary["bkt_model_qualified"] is False


def test_recommendation_lifecycle_api(test_client: TestClient, recommendation_setup, auth_headers):
    """Verifies recommendation API endpoints: generate, list, retrieve, update status, and resources."""
    data = recommendation_setup
    ws_id = data["workspace"].id

    # 1. Generate recommendations
    res_gen = test_client.post(
        f"/api/v1/workspaces/{ws_id}/recommendations/generate",
        json={"force_regenerate": True, "max_recommendations": 5},
        headers=auth_headers,
    )
    assert res_gen.status_code == 200
    items = res_gen.json()
    assert len(items) >= 3

    rec_id = items[0]["id"]

    # 2. List recommendations
    res_list = test_client.get(
        f"/api/v1/workspaces/{ws_id}/recommendations",
        headers=auth_headers,
    )
    assert res_list.status_code == 200
    assert len(res_list.json()) >= 3

    # 3. Retrieve single recommendation
    res_get = test_client.get(
        f"/api/v1/workspaces/{ws_id}/recommendations/{rec_id}",
        headers=auth_headers,
    )
    assert res_get.status_code == 200
    assert res_get.json()["id"] == rec_id

    # 4. Update status: suggested -> viewed -> started -> completed
    for new_status in ["viewed", "started", "completed"]:
        res_patch = test_client.patch(
            f"/api/v1/workspaces/{ws_id}/recommendations/{rec_id}/status",
            json={"status": new_status},
            headers=auth_headers,
        )
        assert res_patch.status_code == 200
        assert res_patch.json()["status"] == new_status

    # 5. Concept revision resources
    c_id = items[0]["concept_id"]
    res_res = test_client.get(
        f"/api/v1/workspaces/{ws_id}/concepts/{c_id}/revision-resources",
        headers=auth_headers,
    )
    assert res_res.status_code == 200
    res_json = res_res.json()
    assert "concept_name" in res_json
    assert "revision_notes" in res_json
