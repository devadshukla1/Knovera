"""Unit and integration tests for C10.3 Research Methodology Extraction."""

import json
from typing import Dict, List, Optional
import uuid
import pytest
from sqlalchemy.orm import Session

from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.ml.research.methodology_extractor import ResearchMethodologyExtractor


@pytest.fixture
def sample_methodology_document(db_session: Session, test_workspace: Workspace, test_user: User):
    """Creates a sample document with detailed methodology chunks."""
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="neural_ir_benchmark.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/neural_ir.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1048576,
        sha256="m" * 64,
        processing_status="completed",
        page_count=12,
        pipeline_version="v1.0",
        extraction_metadata={},
    )
    db_session.add(doc)
    db_session.flush()

    # Methodology Overview & Dataset Chunk
    chunk_0 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        content=(
            "3. METHODOLOGY AND EXPERIMENTAL SETUP\n"
            "This study employs a quantitative computational experimental design to benchmark dense retrieval.\n\n"
            "3.1 Datasets\n"
            "We conduct evaluations on the MS MARCO passage ranking dataset containing approximately 500,000 queries "
            "and 8.8 million candidate passages. Data splits follow standard 80/10/10 train, development, and test partitions.\n"
            "A secondary synthetic dataset of 12,500 domain-specific medical queries was compiled between Jan 2024 and Jun 2024."
        ),
        content_hash="meth_hash0",
        page_start=3,
        page_end=3,
        section_title="3. Methodology",
        token_count=130,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    # Models, Variables, Setup, Metrics, Limitations Chunk
    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=1,
        content=(
            "3.2 Models and Variables\n"
            "The independent variable is the embedding dimension (d=128 vs d=768), while the dependent variable is Mean Reciprocal Rank (MRR@10).\n"
            "We executed fine-tuning on ColBERTv2 and BGE-large-en. "
            "Additionally, we propose a graph-augmented multi-hop router for future investigation.\n\n"
            "3.3 Experimental Hyperparameters\n"
            "All models were trained using PyTorch 2.3 and HuggingFace Transformers on 4 NVIDIA A100 GPUs (80GB). "
            "We used AdamW optimizer with a learning rate of 2e-5, batch size of 64, and weight decay of 0.01 across 5 epochs with random seed 42.\n\n"
            "3.4 Evaluation Metrics and Limitations\n"
            "Evaluation metrics include MRR@10 and Recall@100 computed independently from model outputs.\n"
            "A limitation of this work is that all experiments were restricted to English queries, leaving multilingual robustness unverified."
        ),
        content_hash="meth_hash1",
        page_start=4,
        page_end=4,
        section_title="3.2 Models and Variables",
        token_count=190,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    db_session.add_all([chunk_0, chunk_1])
    db_session.commit()

    return doc, [chunk_0, chunk_1]


def test_deterministic_methodology_extraction(db_session: Session, sample_methodology_document):
    """Verifies regex heuristics extract research approach, dataset details, hyperparameters, and metrics."""
    doc, chunks = sample_methodology_document

    extractor = ResearchMethodologyExtractor(llm_manager=None, enable_llm=False)
    profile = extractor.extract_from_document(doc, chunks)

    # 1. Approach and Design
    assert any("quantitative" in a.lower() or "computational" in a.lower() for a in profile.research_approaches)
    assert len(profile.research_designs) > 0

    # 2. Datasets
    assert len(profile.datasets) >= 1
    ms_marco = next((d for d in profile.datasets if "marco" in d.name.lower()), profile.datasets[0])
    assert ms_marco.name is not None
    assert ms_marco.sample_size_approx is True or ms_marco.sample_size is not None

    # 3. Metrics
    assert len(profile.evaluation_metrics) >= 1
    metric_names = [m.name.upper() for m in profile.evaluation_metrics]
    assert any("MRR" in m or "RECALL" in m for m in metric_names)

    # 4. Limitations
    assert len(profile.limitations) >= 1
    assert any("english" in lim.limitation_text.lower() or "multilingual" in lim.limitation_text.lower() for lim in profile.limitations)


def test_llm_assisted_methodology_extraction_with_proposed_vs_executed(db_session: Session, sample_methodology_document):
    """Verifies LLM extraction correctly classifies proposed vs executed methods and detailed variables."""
    doc, chunks = sample_methodology_document

    mock_llm_data = {
        "research_approaches": ["quantitative", "computational"],
        "research_designs": ["empirical_benchmark"],
        "study_setting": "laboratory",
        "datasets": [
            {
                "name": "MS MARCO Passage Ranking",
                "sample_size": 500000,
                "sample_size_approx": True,
                "unit": "queries",
                "split": {"train": "80%", "dev": "10%", "test": "10%"},
                "collection_period": "Historical benchmark",
                "evidence_text": "MS MARCO passage ranking dataset containing approximately 500,000 queries",
            }
        ],
        "variables": [
            {
                "name": "Embedding Dimension",
                "variable_type": "independent",
                "measurement": "d=128 vs d=768",
                "evidence_text": "The independent variable is the embedding dimension (d=128 vs d=768)",
            },
            {
                "name": "MRR@10",
                "variable_type": "dependent",
                "measurement": "Mean Reciprocal Rank of first relevant passage within top 10",
                "evidence_text": "dependent variable is Mean Reciprocal Rank (MRR@10)",
            }
        ],
        "methods_and_models": [
            {
                "name": "ColBERTv2",
                "method_category": "deep_learning",
                "execution_status": "executed",
                "description": "Late-interaction neural passage retriever",
                "evidence_text": "We executed fine-tuning on ColBERTv2",
            },
            {
                "name": "Graph-Augmented Multi-Hop Router",
                "method_category": "deep_learning",
                "execution_status": "proposed",
                "description": "Router proposed for future work",
                "evidence_text": "we propose a graph-augmented multi-hop router for future investigation",
            }
        ],
        "tools_and_instruments": [
            {
                "name": "PyTorch 2.3",
                "tool_type": "software",
                "evidence_text": "trained using PyTorch 2.3",
            }
        ],
        "experimental_setup": {
            "hyperparameters": {
                "learning_rate": "2e-5",
                "batch_size": 64,
                "weight_decay": 0.01,
                "epochs": 5,
            },
            "hardware_config": "4 NVIDIA A100 GPUs (80GB)",
            "random_seeds": [42],
            "evidence_text": "AdamW optimizer with a learning rate of 2e-5",
        },
        "evaluation_metrics": [
            {
                "name": "MRR@10",
                "category": "ranking",
                "definition": "Mean Reciprocal Rank at cutoff 10",
                "evidence_text": "Evaluation metrics include MRR@10",
            }
        ],
        "limitations": [
            {
                "limitation_text": "All experiments restricted to English queries",
                "category": "generalizability",
                "is_author_stated": True,
                "evidence_text": "restricted to English queries, leaving multilingual robustness unverified",
            }
        ],
    }

    mock_provider = MockLLMProvider(default_response=json.dumps(mock_llm_data))
    manager = LLMManager.get_instance()
    manager.registry.register("mock", mock_provider)

    extractor = ResearchMethodologyExtractor(llm_manager=manager, enable_llm=True)
    profile = extractor.extract_from_document(doc, chunks)

    # Verify executed vs proposed methods
    assert len(profile.methods_and_models) >= 2
    executed_model = next((m for m in profile.methods_and_models if m.name == "ColBERTv2"), None)
    proposed_model = next((m for m in profile.methods_and_models if "Graph" in m.name), None)

    assert executed_model is not None
    assert executed_model.execution_status == "executed"

    assert proposed_model is not None
    assert proposed_model.execution_status == "proposed"

    # Verify variables
    assert len(profile.variables) == 2
    indep_var = next(v for v in profile.variables if v.variable_type == "independent")
    assert indep_var.name == "Embedding Dimension"

    dep_var = next(v for v in profile.variables if v.variable_type == "dependent")
    assert "MRR" in dep_var.name

    # Verify provenance
    assert profile.datasets[0].evidence is not None
    assert len(profile.datasets[0].evidence) > 0
    assert profile.datasets[0].evidence[0].document_id == str(doc.id)


def test_missing_methodology_handling(db_session: Session, test_workspace: Workspace, test_user: User):
    """Verifies document with no methodology sections does not crash or hallucinate."""
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="plain_essay.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/essay.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=1000,
        sha256="0" * 64,
        processing_status="completed",
        page_count=1,
        pipeline_version="v1.0",
        extraction_metadata={},
    )
    chunk = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        content="This is a reflective personal essay discussing the cultural beauty of literature.",
        content_hash="essay_hash",
        page_start=1,
        page_end=1,
        section_title="Essay",
        token_count=15,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )
    db_session.add_all([doc, chunk])
    db_session.commit()

    extractor = ResearchMethodologyExtractor(llm_manager=None, enable_llm=False)
    profile = extractor.extract_from_document(doc, [chunk])

    assert profile.validation_status == "needs_review"
    assert len(profile.datasets) == 0
    assert len(profile.methods_and_models) == 0
    assert len(profile.experimental_setup.hyperparameters) == 0
