"""Unit and integration tests for Multi-Paper Comparison (Phase 10 C10.4).

Validates:
- Workspace isolation and tenancy enforcement
- Document selection bounds (min 2, max 10)
- 7-dimension comparison matrix construction
- Difference summary extraction with grounded evidence
- REST API endpoints for comparison management and matrix retrieval
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.ml.research.comparison_service import MultiPaperComparisonService
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.research_intelligence import (
    ResearchMetadataProfile,
    ResearchMethodologyProfile,
    ResearchObjectiveProfile,
)
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.schemas.research_intelligence import (
    ResearchComparisonCreateRequest,
)


@pytest.fixture
def two_research_docs(db_session: Session, test_workspace: Workspace, test_user: User):
    """Creates two research documents with complete metadata, objective, and methodology profiles."""
    doc_a = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="paper_a.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/paper_a.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1024000,
        sha256="1" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Paper A: Supervised Learning"},
    )
    doc_b = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="paper_b.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/paper_b.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1048000,
        sha256="2" * 64,
        processing_status="completed",
        pipeline_version="v1.0",
        extraction_metadata={"file_title": "Paper B: Self-Supervised Learning"},
    )
    db_session.add_all([doc_a, doc_b])
    db_session.flush()

    # Profiles for Paper A
    meta_a = ResearchMetadataProfile(
        workspace_id=test_workspace.id,
        document_id=doc_a.id,
        title="Supervised Baseline",
        publication_year=2021,
        journal_name="Nature Machine Intelligence",
        doi="10.1000/182",
        authors=[{"name": "Alice Smith"}],
        metadata_fields={"doi": "10.1000/182"},
    )
    obj_a = ResearchObjectiveProfile(
        workspace_id=test_workspace.id,
        document_id=doc_a.id,
        primary_objective="Benchmark supervised learning on ImageNet.",
        problem_statement="High data labeling cost.",
        research_questions=[{"question": "How accurate is supervised learning?"}],
        hypotheses=[{"hypothesis": "Supervised model reaches 85% accuracy."}],
    )
    meth_a = ResearchMethodologyProfile(
        workspace_id=test_workspace.id,
        document_id=doc_a.id,
        research_approaches=["quantitative"],
        research_designs=["experimental"],
        datasets=[
            {
                "name": "ImageNet-1K",
                "sample_size": 1200000,
                "unit": "images",
                "split": {"training": "80%", "validation": "20%"},
                "execution_status": "executed",
            }
        ],
        methods_and_models=[
            {
                "name": "ResNet-50",
                "method_category": "deep_learning",
                "execution_status": "executed",
            }
        ],
        evaluation_metrics=[{"name": "Accuracy", "unit": "%"}],
        limitations=[{"description": "Requires labeled data"}],
    )

    # Profiles for Paper B
    meta_b = ResearchMetadataProfile(
        workspace_id=test_workspace.id,
        document_id=doc_b.id,
        title="Self-Supervised Advancements",
        publication_year=2023,
        conference_name="NeurIPS",
        arxiv_id="2301.12345",
        authors=[{"name": "Bob Jones"}],
        metadata_fields={"arxiv_id": "2301.12345"},
    )
    obj_b = ResearchObjectiveProfile(
        workspace_id=test_workspace.id,
        document_id=doc_b.id,
        primary_objective="Eliminate annotations with contrastive SSL.",
        problem_statement="Unsupervised representation learning.",
        research_questions=[{"question": "Can SSL surpass supervised pretraining?"}],
        hypotheses=[{"hypothesis": "SSL achieves 88% accuracy without labels."}],
    )
    meth_b = ResearchMethodologyProfile(
        workspace_id=test_workspace.id,
        document_id=doc_b.id,
        research_approaches=["quantitative"],
        research_designs=["experimental"],
        datasets=[
            {
                "name": "ImageNet-1K",
                "sample_size": 1200000,
                "unit": "images",
                "execution_status": "executed",
            }
        ],
        methods_and_models=[
            {
                "name": "SimCLR",
                "method_category": "deep_learning",
                "execution_status": "executed",
            },
            {
                "name": "MAE",
                "method_category": "deep_learning",
                "execution_status": "proposed",
            },
        ],
        evaluation_metrics=[{"name": "Linear Probe Accuracy", "unit": "%"}],
        limitations=[{"description": "Heavy compute requirements"}],
    )

    db_session.add_all([meta_a, obj_a, meth_a, meta_b, obj_b, meth_b])
    db_session.commit()

    return doc_a, doc_b


def test_comparison_selection_bounds(db_session: Session, test_workspace: Workspace, two_research_docs):
    """Validates boundary conditions: reject < 2 documents and reject > 10 documents."""
    doc_a, _ = two_research_docs
    service = MultiPaperComparisonService(max_documents=5)

    # Test reject < 2 docs at schema validation
    with pytest.raises(Exception):
        ResearchComparisonCreateRequest(document_ids=[doc_a.id])

    # Test reject > max_documents
    fake_ids = [uuid.uuid4() for _ in range(6)]
    with pytest.raises(ValueError, match="Exceeded maximum allowed documents"):
        service.create_comparison(
            db_session,
            test_workspace.id,
            ResearchComparisonCreateRequest(document_ids=fake_ids),
        )


def test_comparison_workspace_isolation(db_session: Session, test_workspace: Workspace, two_research_docs):
    """Ensures documents from other workspaces cannot be compared."""
    doc_a, doc_b = two_research_docs
    other_ws_id = uuid.uuid4()
    service = MultiPaperComparisonService()

    with pytest.raises(ValueError, match="unauthorized in this workspace"):
        service.create_comparison(
            db_session,
            other_ws_id,
            ResearchComparisonCreateRequest(document_ids=[doc_a.id, doc_b.id]),
        )


def test_comparison_service_matrix_construction(db_session: Session, test_workspace: Workspace, two_research_docs):
    """Verifies that 7 dimensions are populated with executed vs proposed status preserved."""
    doc_a, doc_b = two_research_docs
    service = MultiPaperComparisonService()

    comp = service.create_comparison(
        db_session,
        test_workspace.id,
        ResearchComparisonCreateRequest(
            document_ids=[doc_a.id, doc_b.id],
            title="Supervised vs SSL Comparison",
        ),
    )

    assert comp.id is not None
    assert comp.title == "Supervised vs SSL Comparison"
    assert len(comp.document_ids) == 2

    # Check matrix
    matrix = comp.matrix
    for dim in ["metadata", "objectives", "methodology", "datasets", "models", "evaluation", "limitations"]:
        assert dim in matrix
        assert str(doc_a.id) in matrix[dim]
        assert str(doc_b.id) in matrix[dim]

    # Verify model dimension execution status
    models_cell_b = matrix["models"][str(doc_b.id)]
    assert "SimCLR" in models_cell_b["display_text"]
    assert "MAE" in models_cell_b["display_text"]
    assert "SimCLR" in models_cell_b["value"]["executed"]
    assert "MAE" in models_cell_b["value"]["proposed"]

    # Verify difference summaries
    assert len(comp.difference_summaries) >= 3
    dims = [d["dimension"] for d in comp.difference_summaries]
    assert "objectives" in dims
    assert "models" in dims


def test_comparison_api_endpoints(
    test_client: TestClient,
    test_workspace: Workspace,
    two_research_docs,
    auth_headers: dict,
):
    """Tests the REST API endpoints for C10.4."""
    doc_a, doc_b = two_research_docs

    # 1. Create comparison
    create_url = f"/api/v1/workspaces/{test_workspace.id}/research-comparisons"
    res = test_client.post(
        create_url,
        headers=auth_headers,
        json={
            "document_ids": [str(doc_a.id), str(doc_b.id)],
            "title": "API Multi-Paper Comparison",
        },
    )
    assert res.status_code == 201, res.text
    created = res.json()
    comp_id = created["id"]
    assert created["title"] == "API Multi-Paper Comparison"
    assert len(created["dimensions"]) >= 7

    # 2. List comparisons
    list_url = f"/api/v1/workspaces/{test_workspace.id}/research-comparisons"
    list_res = test_client.get(list_url, headers=auth_headers)
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) >= 1
    assert any(i["id"] == comp_id for i in items)

    # 3. Get comparison by ID
    get_url = f"/api/v1/workspaces/{test_workspace.id}/research-comparisons/{comp_id}"
    get_res = test_client.get(get_url, headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == comp_id

    # 4. Get structured matrix
    matrix_url = f"/api/v1/workspaces/{test_workspace.id}/research-comparisons/{comp_id}/matrix"
    mat_res = test_client.get(matrix_url, headers=auth_headers)
    assert mat_res.status_code == 200
    mat_data = mat_res.json()
    assert mat_data["comparison_id"] == comp_id
    assert len(mat_data["documents"]) == 2
    assert len(mat_data["rows"]) >= 7
