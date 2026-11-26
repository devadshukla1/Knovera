"""Unit and integration tests for Research Finding Extraction and Alignment (Phase 10 C10.5).

Validates:
- Empirical finding extraction from Results/Discussion/Evaluation sections
- Finding taxonomy (quantitative, qualitative, null_result, comparative)
- Statistical significance (p-values, 95% CI) and numeric normalization
- Strict contextual comparability checks (metric compatibility, dataset alignment)
- REST API endpoints for finding extraction and pairwise alignment
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.ml.research.finding_service import ResearchFindingService
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.research_intelligence import (
    ResearchComparisonProfile,
    ResearchFinding,
    ResearchFindingComparison,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.fixture
def finding_test_setup(db_session: Session, test_workspace: Workspace, test_user: User):
    """Sets up two research documents with Results chunks containing quantitative and null findings."""
    doc_1 = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="study_transformer.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/study_transformer.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=512000,
        sha256="3" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Transformer Study"},
    )
    doc_2 = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="study_lstm.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/study_lstm.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=512000,
        sha256="4" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "LSTM Study"},
    )
    db_session.add_all([doc_1, doc_2])
    db_session.flush()

    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc_1.id,
        chunk_index=0,
        section_title="Results and Discussion",
        content=(
            "On the WMT 2014 English-to-German translation task, the big transformer model achieved a BLEU score of 28.4 points, "
            "improving over existing baselines with statistical significance p < 0.01 and 95% CI: [27.9, 28.9]. "
            "On English-to-French, our model achieved an accuracy of 92.5% on the validation set."
        ),
        content_hash="hash_c1",
        page_start=5,
        page_end=5,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    chunk_2 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc_2.id,
        chunk_index=0,
        section_title="Evaluation and Results",
        content=(
            "On the WMT 2014 English-to-German translation benchmark, the recurrent architecture achieved a BLEU score of 24.1 points. "
            "However, in ablation tests we found no statistically significant difference when scaling memory cells beyond 512 dimensions (p > 0.05)."
        ),
        content_hash="hash_c2",
        page_start=7,
        page_end=7,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )
    db_session.add_all([chunk_1, chunk_2])

    comp = ResearchComparisonProfile(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        created_by_user_id=test_user.id,
        title="Transformer vs LSTM Comparison",
        document_ids=[str(doc_1.id), str(doc_2.id)],
        document_versions={str(doc_1.id): "v1.0", str(doc_2.id): "v1.0"},
        dimensions=["metadata", "evaluation"],
        matrix={},
        difference_summaries=[],
    )
    db_session.add(comp)
    db_session.commit()

    return doc_1, doc_2, [chunk_1], [chunk_2], comp


def test_finding_extraction_service(db_session: Session, finding_test_setup):
    """Tests extraction of quantitative findings, significance, and null results."""
    doc_1, doc_2, chunks_1, chunks_2, _ = finding_test_setup
    service = ResearchFindingService(enable_llm=False)

    # Extract for Doc 1
    findings_1 = service.extract_findings_for_document(db_session, doc_1, chunks_1)
    assert len(findings_1) >= 1
    bleu_finding = next((f for f in findings_1 if "bleu" in (f.metric or "").lower()), None)
    assert bleu_finding is not None
    assert bleu_finding.finding_type == "quantitative"
    assert bleu_finding.numeric_value == pytest.approx(28.4, rel=1e-2)
    assert bleu_finding.statistical_significance is not None
    assert "p < 0.01" in bleu_finding.statistical_significance
    assert bleu_finding.confidence_interval is not None
    assert len(bleu_finding.evidence) >= 1

    # Extract for Doc 2
    findings_2 = service.extract_findings_for_document(db_session, doc_2, chunks_2)
    assert len(findings_2) >= 1
    null_finding = next((f for f in findings_2 if f.finding_type == "null_result"), None)
    assert null_finding is not None
    assert null_finding.direction == "null"


def test_contextual_comparability_rules(db_session: Session, test_workspace: Workspace, finding_test_setup):
    """Validates comparability safeguards: incompatible metrics and distinct datasets."""
    doc_1, doc_2, _, _, comp = finding_test_setup
    service = ResearchFindingService(enable_llm=False)

    # 1. Compatible metrics and same dataset: Comparable
    f1 = ResearchFinding(
        workspace_id=test_workspace.id,
        document_id=doc_1.id,
        document_version="v1.0",
        finding_type="quantitative",
        original_statement="Achieved 82% F1 on SQuAD v2",
        normalized_statement="F1 score of 82.0% on SQuAD v2",
        outcome_variable="Reading Comprehension",
        metric="F1",
        numeric_value=82.0,
        unit="%",
        dataset_relationship="SQuAD v2",
        direction="positive",
    )
    f2 = ResearchFinding(
        workspace_id=test_workspace.id,
        document_id=doc_2.id,
        document_version="v1.0",
        finding_type="quantitative",
        original_statement="Obtained 85% F1 on SQuAD v2",
        normalized_statement="F1 score of 85.0% on SQuAD v2",
        outcome_variable="Reading Comprehension",
        metric="F1",
        numeric_value=85.0,
        unit="%",
        dataset_relationship="SQuAD v2",
        direction="positive",
    )

    # 2. Incompatible metrics (F1 vs Accuracy)
    f3_acc = ResearchFinding(
        workspace_id=test_workspace.id,
        document_id=doc_2.id,
        document_version="v1.0",
        finding_type="quantitative",
        original_statement="Obtained 85% Accuracy on SQuAD v2",
        normalized_statement="Accuracy of 85.0% on SQuAD v2",
        outcome_variable="Reading Comprehension",
        metric="Accuracy",
        numeric_value=85.0,
        unit="%",
        dataset_relationship="SQuAD v2",
        direction="positive",
    )

    # 3. Different datasets (SQuAD vs HotpotQA)
    f4_diff_ds = ResearchFinding(
        workspace_id=test_workspace.id,
        document_id=doc_2.id,
        document_version="v1.0",
        finding_type="quantitative",
        original_statement="Achieved 85% F1 on HotpotQA",
        normalized_statement="F1 score of 85.0% on HotpotQA",
        outcome_variable="Reading Comprehension",
        metric="F1",
        numeric_value=85.0,
        unit="%",
        dataset_relationship="HotpotQA",
        direction="positive",
    )

    db_session.add_all([f1, f2, f3_acc, f4_diff_ds])
    db_session.commit()

    # Rule 1: Compatible pair
    aligned, status, prelim, rationale, diffs = service._compare_findings_heuristics(f1, f2)
    assert aligned is True
    assert status == "comparable"

    # Rule 2: Incompatible metrics check
    aligned, status, prelim, rationale, diffs = service._compare_findings_heuristics(f1, f3_acc)
    assert status == "incompatible_metrics"
    assert "incompatible metrics" in rationale.lower()

    # Rule 3: Different datasets check
    aligned, status, prelim, rationale, diffs = service._compare_findings_heuristics(f1, f4_diff_ds)
    assert status == "different_conditions"
    assert "distinct datasets" in rationale.lower()


def test_finding_api_endpoints(
    test_client: TestClient,
    test_workspace: Workspace,
    finding_test_setup,
    auth_headers: dict,
):
    """Tests finding extraction, retrieval, and alignment API endpoints."""
    doc_1, doc_2, _, _, comp = finding_test_setup

    # 1. Extract findings for doc_1
    ext_url = f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_1.id}/research-findings/extract"
    res = test_client.post(ext_url, headers=auth_headers)
    assert res.status_code == 200, res.text
    findings_1 = res.json()
    assert len(findings_1) >= 1

    # Extract findings for doc_2
    ext_url_2 = f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_2.id}/research-findings/extract"
    res_2 = test_client.post(ext_url_2, headers=auth_headers)
    assert res_2.status_code == 200
    assert len(res_2.json()) >= 1

    # 2. List findings for doc_1
    list_url = f"/api/v1/workspaces/{test_workspace.id}/documents/{doc_1.id}/research-findings"
    get_res = test_client.get(list_url, headers=auth_headers)
    assert get_res.status_code == 200
    assert len(get_res.json()) >= 1

    # 3. Align findings for comparison
    align_url = f"/api/v1/workspaces/{test_workspace.id}/research-comparisons/{comp.id}/align-findings"
    align_res = test_client.post(align_url, headers=auth_headers)
    assert align_res.status_code == 200, align_res.text
    relations = align_res.json()
    assert len(relations) >= 1

    # 4. List aligned relations
    rel_url = f"/api/v1/workspaces/{test_workspace.id}/research-comparisons/{comp.id}/finding-relations"
    rel_res = test_client.get(rel_url, headers=auth_headers)
    assert rel_res.status_code == 200
    assert len(rel_res.json()) == len(relations)
