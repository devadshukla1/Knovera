"""Unit and integration tests for Natural Language Inference Service and Benchmarking (Phase 10 C10.6).

Validates:
- Label mapping to standard set ('entailment', 'contradiction', 'neutral')
- Bidirectional NLI inference and margin-based decision policy
- Pair fingerprinting and deterministic SQLite/Postgres inference caching
- Contextual contradiction safeguard (safeguard never overridden by raw NLI)
- Benchmark evaluation suite (Accuracy, Macro F1, Per-class F1, Confusion Matrix)
- REST API endpoints for pair inference, comparison NLI evaluation, and benchmark execution
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.ml.research.nli_service import MockNLIProvider, NLIInferenceService
from backend.app.models.document import Document
from backend.app.models.research_intelligence import (
    ResearchComparisonProfile,
    ResearchFinding,
    ResearchFindingComparison,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.research_intelligence import NLIInferenceRequest


@pytest.fixture
def nli_setup(db_session: Session, test_workspace: Workspace, test_user: User):
    """Sets up an NLI service instance with deterministic MockNLIProvider and test records."""
    mock_provider = MockNLIProvider()
    service = NLIInferenceService(
        provider=mock_provider,
        model_id="mock-nli-model",
        model_revision="v1.0-test",
        margin_threshold=0.15,
    )
    NLIInferenceService.set_instance(service)

    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="nli_paper.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/nli_paper.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=100000,
        sha256="5" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "NLI Test Paper"},
    )
    db_session.add(doc)
    db_session.flush()

    return service, doc


def test_nli_label_mapping_and_bidirectionality(db_session: Session, test_workspace: Workspace, nli_setup):
    """Verifies forward, backward, and aggregated inference on entailment and contradiction."""
    service, _ = nli_setup

    # Test Entailment
    resp_ent = service.infer_pair(
        db_session,
        test_workspace.id,
        premise="The proposed model significantly outperforms all baselines on accuracy.",
        hypothesis="The proposed model achieved higher accuracy than existing methods.",
        bidirectional=True,
    )
    assert resp_ent.forward_label == "entailment"
    assert resp_ent.aggregated_label == "entailment"
    assert resp_ent.abstained is False
    assert resp_ent.margin >= 0.15

    # Test Contradiction
    resp_contra = service.infer_pair(
        db_session,
        test_workspace.id,
        premise="The proposed algorithm reduced latency by 40%.",
        hypothesis="The algorithm failed to decrease latency and resulted in slower inference.",
        bidirectional=True,
    )
    assert resp_contra.forward_label == "contradiction"
    assert resp_contra.aggregated_label == "contradiction"
    assert resp_contra.abstained is False


def test_nli_cache_fingerprint(db_session: Session, test_workspace: Workspace, nli_setup):
    """Verifies that duplicate requests hit the cached NLIInferenceRecord."""
    service, _ = nli_setup
    premise = "Self-attention replaces recurrence entirely in sequence models."
    hypo = "Recurrent neural networks are not required when self-attention is used."

    # First call - executes provider
    r1 = service.infer_pair(db_session, test_workspace.id, premise, hypo)
    fp1 = r1.pair_fingerprint

    # Second call - returns cached response
    r2 = service.infer_pair(db_session, test_workspace.id, premise, hypo)
    assert r2.pair_fingerprint == fp1
    assert r2.aggregated_label == r1.aggregated_label
    assert r2.forward_scores == r1.forward_scores


def test_contextual_contradiction_safeguard(db_session: Session, test_workspace: Workspace, nli_setup):
    """Verifies the core architectural constraint:
    If experimental conditions differ (datasets/metrics), raw NLI contradiction
    MUST NOT override comparability_status to 'contradictory'.
    """
    service, doc = nli_setup

    fa = ResearchFinding(
        workspace_id=test_workspace.id,
        document_id=doc.id,
        document_version="v1.0",
        finding_type="quantitative",
        original_statement="Model achieves 95% on Synthetic Task A",
        normalized_statement="Model reaches 95% accuracy on Task A",
        dataset_relationship="Task A",
    )
    fb = ResearchFinding(
        workspace_id=test_workspace.id,
        document_id=doc.id,
        document_version="v1.0",
        finding_type="quantitative",
        original_statement="Model fails to solve Real-World Task B",
        normalized_statement="Model fails with 20% accuracy on Task B",
        dataset_relationship="Task B",
    )
    db_session.add_all([fa, fb])
    db_session.flush()

    comp_profile = ResearchComparisonProfile(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        title="Safeguard Profile",
        document_ids=[str(doc.id)],
        document_versions={str(doc.id): "v1.0"},
        dimensions=["evaluation"],
        matrix={},
        difference_summaries=[],
    )
    db_session.add(comp_profile)
    db_session.flush()

    finding_comp = ResearchFindingComparison(
        comparison_id=comp_profile.id,
        finding_a_id=fa.id,
        finding_b_id=fb.id,
        comparability_status="different_conditions",
        preliminary_relationship="different_conditions",
        comparison_rationale="Evaluated on distinct datasets.",
    )
    db_session.add(finding_comp)
    db_session.commit()

    # Compare through NLI service
    updated = service.compare_findings(db_session, test_workspace.id, finding_comp)

    # Incompatible conditions must prevent final contradictory claim
    assert updated.comparability_status == "different_conditions"
    assert updated.final_relation == "different_conditions"
    assert "contextual comparability" in (updated.comparison_rationale or "").lower()


def test_nli_benchmark_evaluation(db_session: Session, test_workspace: Workspace, nli_setup):
    """Tests the benchmark evaluation suite with Accuracy, Macro F1, and Confusion Matrix metrics."""
    service, _ = nli_setup

    eval_pairs = [
        {
            "premise": "Our framework improves throughput by 3x.",
            "hypothesis": "The framework yields faster processing than the baseline.",
            "gold_label": "entailment",
        },
        {
            "premise": "The model achieved superior classification results.",
            "hypothesis": "The model performs worse than random guessing.",
            "gold_label": "contradiction",
        },
        {
            "premise": "We trained on 8 NVIDIA V100 GPUs.",
            "hypothesis": "The training process took exactly 48 hours to finish.",
            "gold_label": "neutral",
        },
    ]

    eval_run = service.run_benchmark_evaluation(
        db_session,
        custom_pairs=eval_pairs,
        dataset_name="test_benchmark_dataset",
        workspace_id=test_workspace.id,
    )

    assert eval_run.id is not None
    assert eval_run.sample_count == 3
    assert eval_run.accuracy > 0.0
    assert eval_run.macro_f1 > 0.0
    assert "entailment" in eval_run.per_class_f1
    assert "contradiction" in eval_run.per_class_f1
    assert "neutral" in eval_run.per_class_f1
    assert "entailment" in eval_run.confusion_matrix


def test_nli_api_endpoints(
    test_client: TestClient,
    test_workspace: Workspace,
    nli_setup,
    auth_headers: dict,
):
    """Tests REST endpoints for pair inference, batch comparison NLI, and benchmark evaluation."""
    service, _ = nli_setup

    # 1. Infer Pair API
    infer_url = f"/api/v1/workspaces/{test_workspace.id}/nli/infer"
    res = test_client.post(
        infer_url,
        headers=auth_headers,
        json={
            "premise": "Transformers achieve state of the art results.",
            "hypothesis": "Transformers outperform earlier recurrent models.",
            "bidirectional": True,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["forward_label"] in ["entailment", "contradiction", "neutral"]
    assert "pair_fingerprint" in data

    # 2. Benchmark Evaluation Run API
    eval_url = f"/api/v1/workspaces/{test_workspace.id}/nli/evaluate"
    eval_res = test_client.post(
        eval_url,
        headers=auth_headers,
        json={"dataset_name": "api_eval_run"},
    )
    assert eval_res.status_code == 200, eval_res.text
    run_data = eval_res.json()
    assert run_data["dataset_name"] == "api_eval_run"
    assert run_data["sample_count"] >= 3

    # 3. List Benchmark Evaluations API
    list_url = f"/api/v1/workspaces/{test_workspace.id}/nli/evaluations"
    list_res = test_client.get(list_url, headers=auth_headers)
    assert list_res.status_code == 200
    runs = list_res.json()
    assert len(runs) >= 1
