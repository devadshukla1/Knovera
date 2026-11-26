"""Unit and Integration Tests for Research Objective Extraction (Phase 10 C10.2).

Tests:
- Primary and secondary objective identification
- Research questions extraction
- Directional, alternative, and null hypotheses extraction
- Problem statement, motivation, scope, and claimed contributions distinction
- Concept linking to Phase 7 Knowledge Nodes
- Objective normalization (original vs normalized)
- Missing and ambiguous objective handling
"""

import json
import uuid
import pytest
from sqlalchemy.orm import Session

from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.ml.research.objective_extractor import ResearchObjectiveExtractor
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.user import User
from backend.app.models.workspace import Workspace


@pytest.fixture
def sample_academic_document(db_session: Session, test_workspace: Workspace, test_user: User):
    """Creates a sample academic document with problem statement, objectives, RQs, and hypotheses."""
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="information_retrieval_nli_evaluation.pdf",
        storage_key=f"ws-{test_workspace.id}/docs/ir_nli.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=890000,
        sha256="c" * 64,
        processing_status="completed",
        page_count=10,
        pipeline_version="v1.0",
        extraction_metadata={},
    )
    db_session.add(doc)
    db_session.flush()

    # Introduction & Problem Statement Chunk
    chunk_0 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        content=(
            "1. INTRODUCTION & PROBLEM STATEMENT\n"
            "Modern RAG systems frequently suffer from factual hallucination and unfaithful citations. "
            "The main motivation of this research is that existing lexical metrics fail to detect subtle semantic contradictions. "
            "Therefore, the primary objective of this study is to evaluate the effectiveness of cross-encoder natural language inference (NLI) "
            "in verifying generated claims against retrieved academic chunks.\n\n"
            "Our secondary objective is to benchmark latency trade-offs between bi-encoders and cross-encoders."
        ),
        content_hash="obj_hash0",
        page_start=1,
        page_end=1,
        section_title="1. Introduction",
        token_count=140,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    # Research Questions & Hypotheses Chunk
    chunk_1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=1,
        content=(
            "2. RESEARCH QUESTIONS AND HYPOTHESES\n"
            "RQ1: To what extent does cross-encoder reranking improve claim verification accuracy?\n"
            "RQ2: Can quantization reduce inference latency without degrading classification F1-score?\n\n"
            "Hypothesis H1: We hypothesize that NLI verification significantly reduces citation hallucination rates compared to BM25 baselines.\n"
            "Hypothesis H0: There is no statistically significant difference between bi-encoder and cross-encoder contradiction detection.\n\n"
            "In summary, this paper makes the following contributions: "
            "(1) An audited dataset of 1,200 peer-reviewed premise-hypothesis pairs; "
            "(2) A fine-tuned cross-encoder NLI model with 89.4% Macro F1."
        ),
        content_hash="obj_hash1",
        page_start=2,
        page_end=2,
        section_title="2. Research Questions",
        token_count=170,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )

    # Create Phase 7 Knowledge Nodes for concept matching
    node_nli = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        name="Natural Language Inference",
        normalized_name="natural language inference",
        node_type="concept",
        category="algorithm",
        description="Task of determining logical relationship between sentences",
    )
    node_cross = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        name="Cross-Encoder",
        normalized_name="cross-encoder",
        node_type="concept",
        category="architecture",
        description="Model processing query and document concatenated together",
    )

    db_session.add_all([chunk_0, chunk_1, node_nli, node_cross])
    db_session.commit()

    return doc, [chunk_0, chunk_1], [node_nli, node_cross]


def test_deterministic_objective_extraction(db_session: Session, sample_academic_document):
    """Verifies deterministic regex heuristics extract primary objective, RQs, hypotheses, and contributions."""
    doc, chunks, nodes = sample_academic_document

    extractor = ResearchObjectiveExtractor(llm_manager=None, enable_llm=False)
    profile = extractor.extract_from_document(doc, chunks, known_concepts=nodes)

    # Primary objective
    assert profile.primary_objective is not None
    assert "cross-encoder natural language inference" in profile.primary_objective.lower()

    # Objectives list
    assert len(profile.objectives) >= 1
    assert profile.objectives[0].is_primary is True
    assert profile.objectives[0].objective_type == "primary_objective"

    # Research Questions
    assert len(profile.research_questions) >= 1
    rq_texts = [q.question_text for q in profile.research_questions]
    assert any("cross-encoder reranking improve claim verification" in t for t in rq_texts)

    # Hypotheses
    assert len(profile.hypotheses) >= 1
    hyp_texts = [h.hypothesis_text for h in profile.hypotheses]
    assert any("NLI verification significantly reduces citation hallucination" in t for t in hyp_texts)

    # Claimed Contributions
    assert len(profile.claimed_contributions) >= 1
    cnt_texts = [c.contribution_text for c in profile.claimed_contributions]
    assert any("audited dataset" in t.lower() or "fine-tuned cross-encoder" in t.lower() for t in cnt_texts)


def test_llm_assisted_objective_extraction_and_concept_linking(db_session: Session, sample_academic_document):
    """Verifies LLM extraction organizes objectives, problem statements, hypotheses, and links Knowledge Nodes."""
    doc, chunks, nodes = sample_academic_document

    mock_llm_payload = {
        "primary_objective": "Evaluate the effectiveness of cross-encoder natural language inference (NLI) in verifying generated claims against retrieved academic chunks.",
        "problem_statement": "Modern RAG systems frequently suffer from factual hallucination and unfaithful citations.",
        "motivation": "Existing lexical metrics fail to detect subtle semantic contradictions in academic literature.",
        "research_scope": {
            "domain": "Natural Language Processing",
            "target_population": "Peer-reviewed scientific publications",
            "study_environment": "Automated RAG evaluation pipeline",
            "time_period": "2024",
            "boundaries": ["English-language academic papers"],
            "exclusions": ["Non-peer-reviewed preprints without citations"],
        },
        "objectives": [
            {
                "objective_type": "primary_objective",
                "original_text": "To evaluate the effectiveness of cross-encoder natural language inference (NLI) in verifying generated claims.",
                "normalized_text": "Evaluate cross-encoder NLI claim verification accuracy.",
                "is_primary": True,
                "evidence_text": "the primary objective of this study is to evaluate the effectiveness of cross-encoder natural language inference",
            },
            {
                "objective_type": "secondary_objective",
                "original_text": "Benchmark latency trade-offs between bi-encoders and cross-encoders.",
                "normalized_text": "Analyze inference latency trade-offs.",
                "is_primary": False,
                "evidence_text": "Our secondary objective is to benchmark latency trade-offs",
            },
        ],
        "research_questions": [
            {
                "question_text": "To what extent does cross-encoder reranking improve claim verification accuracy?",
                "normalized_text": "Impact of cross-encoder reranking on claim verification accuracy",
                "evidence_text": "RQ1: To what extent does cross-encoder reranking improve claim verification accuracy?",
            }
        ],
        "hypotheses": [
            {
                "hypothesis_text": "We hypothesize that NLI verification significantly reduces citation hallucination rates compared to BM25 baselines.",
                "hypothesis_type": "directional",
                "evidence_text": "Hypothesis H1: We hypothesize that NLI verification significantly reduces citation hallucination rates",
            },
            {
                "hypothesis_text": "There is no statistically significant difference between bi-encoder and cross-encoder contradiction detection.",
                "hypothesis_type": "null",
                "evidence_text": "Hypothesis H0: There is no statistically significant difference",
            },
        ],
        "claimed_contributions": [
            {
                "contribution_text": "An audited benchmark dataset of 1,200 peer-reviewed premise-hypothesis pairs.",
                "contribution_type": "demonstrated",
                "evidence_text": "An audited dataset of 1,200 peer-reviewed premise-hypothesis pairs",
            }
        ],
    }

    mock_provider = MockLLMProvider(default_response=json.dumps(mock_llm_payload))
    manager = LLMManager.get_instance()
    manager.registry.register("mock", mock_provider)

    extractor = ResearchObjectiveExtractor(llm_manager=manager, enable_llm=True)
    profile = extractor.extract_from_document(doc, chunks, known_concepts=nodes)

    assert "cross-encoder natural language inference" in profile.primary_objective
    assert "factual hallucination" in profile.problem_statement
    assert "Existing lexical metrics fail" in profile.motivation

    # Concept Linking: 'Natural Language Inference' and 'Cross-Encoder' nodes should be linked
    assert len(profile.objectives) == 2
    prim_obj = profile.objectives[0]
    assert prim_obj.is_primary is True
    assert len(prim_obj.associated_concept_ids) > 0

    # Hypotheses
    assert len(profile.hypotheses) == 2
    assert profile.hypotheses[0].hypothesis_type == "directional"
    assert profile.hypotheses[1].hypothesis_type == "null"

    # Evidence
    assert len(prim_obj.evidence) > 0
    assert prim_obj.evidence[0].page_number == 1


def test_missing_objectives_handling(db_session: Session, test_workspace: Workspace, test_user: User):
    """Verifies document with no stated objectives returns validation_status needs_review without hallucinating."""
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        uploaded_by_user_id=test_user.id,
        original_filename="raw_data_dump.txt",
        storage_key=f"ws-{test_workspace.id}/docs/raw.txt",
        media_type="text/plain",
        file_extension=".txt",
        file_size_bytes=5000,
        sha256="d" * 64,
        processing_status="completed",
        page_count=1,
        pipeline_version="v1.0",
        extraction_metadata={},
    )
    db_session.add(doc)
    db_session.flush()

    chunk = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=test_workspace.id,
        document_id=doc.id,
        chunk_index=0,
        content="Table 1: User IDs and raw timestamps from Apache web server logs.",
        content_hash="raw_hash",
        page_start=1,
        page_end=1,
        token_count=15,
        parser_version="v1.0",
        cleaning_version="v1.0",
        chunking_version="v1.0",
    )
    db_session.add(chunk)
    db_session.commit()

    extractor = ResearchObjectiveExtractor(llm_manager=None, enable_llm=False)
    profile = extractor.extract_from_document(doc, [chunk])

    assert profile.primary_objective is None
    assert profile.problem_statement is None
    assert len(profile.objectives) == 0
    assert len(profile.research_questions) == 0
    assert len(profile.hypotheses) == 0
    assert profile.validation_status == "needs_review"
