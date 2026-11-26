"""Tests for Concept-Question Mapping (Phase 9 C9.1).

Covers:
- Explicit mapping creation with validation status and confidence
- Querying concepts for a question and questions for a concept
- Automated candidate concept discovery across MCQ, True/False, and FillBlank
- Updating validation status and confidence score
- Deletion of mappings
- Duplicate mapping prevention
- Workspace boundary isolation
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.learner_intelligence import QuestionConceptMapping
from backend.app.models.study_material import (
    FillBlankExercise,
    MCQOption,
    MCQQuestion,
    TrueFalseQuestion,
)
from backend.app.models.workspace import Workspace


@pytest.fixture
def sample_concept(db_session: Session, test_workspace: Workspace) -> KnowledgeNode:
    """Creates a canonical concept node."""
    node = KnowledgeNode(
        workspace_id=test_workspace.id,
        node_type="concept",
        category="algorithm",
        name="K-Means Clustering",
        normalized_name="kmeans clustering",
        description="An unsupervised centroid-based clustering algorithm.",
        aliases=["kmeans", "k-means algorithm"],
    )
    db_session.add(node)
    db_session.commit()
    db_session.refresh(node)
    return node


@pytest.fixture
def sample_mcq(db_session: Session, test_workspace: Workspace) -> MCQQuestion:
    """Creates an MCQ question mentioning K-Means."""
    mcq = MCQQuestion(
        workspace_id=test_workspace.id,
        question_text="Which algorithm iteratively partitions data into K distinct clusters?",
        difficulty="medium",
        question_type="conceptual",
        correct_option_id="opt_a",
        explanation="K-Means clustering iteratively updates cluster centroids.",
        topic_tags=["unsupervised learning", "clustering"],
        source_references=[],
    )
    db_session.add(mcq)
    db_session.flush()

    opt_a = MCQOption(
        question_id=mcq.id,
        option_id="opt_a",
        option_text="K-Means",
        is_correct=True,
    )
    opt_b = MCQOption(
        question_id=mcq.id,
        option_id="opt_b",
        option_text="Linear Regression",
        is_correct=False,
    )
    db_session.add_all([opt_a, opt_b])
    db_session.commit()
    db_session.refresh(mcq)
    return mcq


@pytest.fixture
def sample_tf(db_session: Session, test_workspace: Workspace) -> TrueFalseQuestion:
    """Creates a True/False question."""
    tf = TrueFalseQuestion(
        workspace_id=test_workspace.id,
        statement="K-Means clustering requires the number of clusters K to be specified in advance.",
        correct_answer=True,
        explanation="A fundamental requirement of K-Means is pre-specifying K.",
        difficulty="easy",
        topic="clustering",
        source_references=[],
    )
    db_session.add(tf)
    db_session.commit()
    db_session.refresh(tf)
    return tf


@pytest.fixture
def sample_fill_blank(db_session: Session, test_workspace: Workspace) -> FillBlankExercise:
    """Creates a Fill-in-the-blank question."""
    fb = FillBlankExercise(
        workspace_id=test_workspace.id,
        sentence_with_blank="In _____ clustering, centroids are recomputed iteratively.",
        original_sentence="In K-Means clustering, centroids are recomputed iteratively.",
        canonical_answer="K-Means",
        accepted_answers=["kmeans", "k-means"],
        difficulty="medium",
        hint="Centroid-based algorithm",
        explanation="Centroids define the center of clusters in K-Means.",
    )
    db_session.add(fb)
    db_session.commit()
    db_session.refresh(fb)
    return fb


def test_create_and_get_explicit_mapping(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    sample_mcq: MCQQuestion,
    sample_concept: KnowledgeNode,
):
    """Test explicit creation of a question-concept mapping."""
    payload = {
        "concept_id": str(sample_concept.id),
        "question_type": "mcq",
        "mapping_method": "explicit_metadata",
        "confidence_score": 1.0,
        "validation_status": "validated",
        "evidence_excerpt": "Directly tested in MCQ stem and explanation.",
    }

    url = f"/api/v1/workspaces/{test_workspace.id}/questions/{sample_mcq.id}/concept-mappings"
    response = test_client.post(url, json=payload, headers=auth_headers)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["concept_id"] == str(sample_concept.id)
    assert data["confidence_score"] == 1.0
    assert data["validation_status"] == "validated"
    assert data["concept"]["name"] == "K-Means Clustering"

    # Query concepts for question
    q_url = f"/api/v1/workspaces/{test_workspace.id}/questions/{sample_mcq.id}/concepts"
    get_res = test_client.get(q_url, headers=auth_headers)
    assert get_res.status_code == 200
    q_data = get_res.json()
    assert q_data["total_mappings"] == 1
    assert q_data["mappings"][0]["concept_id"] == str(sample_concept.id)

    # Query questions for concept
    c_url = f"/api/v1/workspaces/{test_workspace.id}/concepts/{sample_concept.id}/questions"
    c_res = test_client.get(c_url, headers=auth_headers)
    assert c_res.status_code == 200
    c_data = c_res.json()
    assert c_data["total_questions"] == 1
    assert c_data["questions"][0]["question_id"] == str(sample_mcq.id)


def test_duplicate_mapping_prevention(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    sample_mcq: MCQQuestion,
    sample_concept: KnowledgeNode,
):
    """Attempting to map the same concept twice to the same question raises 409 Conflict."""
    payload = {
        "concept_id": str(sample_concept.id),
        "question_type": "mcq",
        "mapping_method": "explicit_metadata",
        "confidence_score": 0.9,
    }
    url = f"/api/v1/workspaces/{test_workspace.id}/questions/{sample_mcq.id}/concept-mappings"
    res1 = test_client.post(url, json=payload, headers=auth_headers)
    assert res1.status_code == 201

    res2 = test_client.post(url, json=payload, headers=auth_headers)
    assert res2.status_code == 409


def test_candidate_generation_mcq_tf_fillblank(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    sample_concept: KnowledgeNode,
    sample_mcq: MCQQuestion,
    sample_tf: TrueFalseQuestion,
    sample_fill_blank: FillBlankExercise,
):
    """Tests automated candidate mapping generation across different question types."""
    # 1. True/False question candidate generation (stem match)
    url_tf = f"/api/v1/workspaces/{test_workspace.id}/questions/{sample_tf.id}/concept-mappings/generate?auto_validate=true"
    res_tf = test_client.post(url_tf, headers=auth_headers)
    assert res_tf.status_code == 200, res_tf.text
    candidates_tf = res_tf.json()
    assert len(candidates_tf) >= 1
    assert any(c["concept_id"] == str(sample_concept.id) for c in candidates_tf)
    assert candidates_tf[0]["validation_status"] == "validated"
    assert candidates_tf[0]["confidence_score"] >= 0.85

    # 2. Fill-in-the-blank candidate generation (original sentence / answer match)
    url_fb = f"/api/v1/workspaces/{test_workspace.id}/questions/{sample_fill_blank.id}/concept-mappings/generate"
    res_fb = test_client.post(url_fb, headers=auth_headers)
    assert res_fb.status_code == 200, res_fb.text
    candidates_fb = res_fb.json()
    assert len(candidates_fb) >= 1
    assert candidates_fb[0]["validation_status"] == "candidate"


def test_update_and_delete_mapping(
    test_client: TestClient,
    auth_headers: dict,
    test_workspace: Workspace,
    sample_tf: TrueFalseQuestion,
    sample_concept: KnowledgeNode,
):
    """Tests updating validation status and confidence, then deleting the mapping."""
    # Create mapping
    payload = {
        "concept_id": str(sample_concept.id),
        "validation_status": "candidate",
        "confidence_score": 0.7,
    }
    create_url = f"/api/v1/workspaces/{test_workspace.id}/questions/{sample_tf.id}/concept-mappings"
    c_res = test_client.post(create_url, json=payload, headers=auth_headers)
    assert c_res.status_code == 201
    mapping_id = c_res.json()["id"]

    # Patch mapping
    patch_url = f"/api/v1/workspaces/{test_workspace.id}/concept-mappings/{mapping_id}"
    patch_payload = {
        "validation_status": "validated",
        "confidence_score": 0.95,
        "evidence_excerpt": "Confirmed by educator review.",
    }
    p_res = test_client.patch(patch_url, json=patch_payload, headers=auth_headers)
    assert p_res.status_code == 200
    p_data = p_res.json()
    assert p_data["validation_status"] == "validated"
    assert p_data["confidence_score"] == 0.95
    assert p_data["evidence_excerpt"] == "Confirmed by educator review."

    # Delete mapping
    del_res = test_client.delete(patch_url, headers=auth_headers)
    assert del_res.status_code == 204

    # Verify deleted
    get_res = test_client.get(
        f"/api/v1/workspaces/{test_workspace.id}/questions/{sample_tf.id}/concepts",
        headers=auth_headers,
    )
    assert get_res.status_code == 200
    assert get_res.json()["total_mappings"] == 0


def test_cross_workspace_isolation(
    test_client: TestClient,
    auth_headers: dict,
    other_auth_headers: dict,
    test_workspace: Workspace,
    sample_mcq: MCQQuestion,
    sample_concept: KnowledgeNode,
):
    """A user in another workspace cannot map questions or access concept mappings."""
    url = f"/api/v1/workspaces/{test_workspace.id}/questions/{sample_mcq.id}/concept-mappings"
    payload = {
        "concept_id": str(sample_concept.id),
        "validation_status": "validated",
    }
    # Other user tries to access test_workspace
    res = test_client.post(url, json=payload, headers=other_auth_headers)
    assert res.status_code in (403, 404)
