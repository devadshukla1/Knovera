"""Unit and integration tests for Knovera Study Material Generators (Phase 8 C8.1-C8.3)."""

import json
import uuid
import pytest

from backend.app.llm.manager import LLMManager
from backend.app.llm.providers.mock import MockLLMProvider
from backend.app.ml.study_materials.fill_blank_generator import FillBlankGenerator
from backend.app.ml.study_materials.mcq_generator import MCQGenerator
from backend.app.ml.study_materials.provenance import (
    build_source_reference,
    find_supporting_chunk,
    format_source_context,
)
from backend.app.ml.study_materials.revision_notes import RevisionNoteGenerator
from backend.app.ml.study_materials.schemas import (
    DetailLevel,
    FillBlankGenerateRequest,
    MCQGenerateRequest,
    MCQType,
    NoteFocus,
    NoteLength,
    QuestionDifficulty,
    RevisionNotesGenerateRequest,
    SourceScope,
    SourceScopeType,
)
from backend.app.ml.study_materials.source_resolver import ResolvedChunk
from backend.app.ml.study_materials.validators import BLANK_PLACEHOLDER


@pytest.fixture
def sample_chunks() -> list[ResolvedChunk]:
    doc_id = uuid.uuid4()
    return [
        ResolvedChunk(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_title="Introduction to Machine Learning",
            chunk_index=0,
            page_number=1,
            heading="Support Vector Machines",
            content="Support Vector Machines (SVMs) are supervised learning algorithms used for classification. The goal of an SVM is to find the optimal hyperplane that maximizes the geometric margin between data classes.",
            token_count=35,
        ),
        ResolvedChunk(
            chunk_id=uuid.uuid4(),
            document_id=doc_id,
            document_title="Introduction to Machine Learning",
            chunk_index=1,
            page_number=2,
            heading="K-Means Clustering",
            content="K-Means is an unsupervised clustering algorithm that partitions n observations into k clusters. Each observation belongs to the cluster with the nearest mean centroid.",
            token_count=30,
        ),
    ]


# =============================================================================
# Provenance & Context Formatting Tests
# =============================================================================

def test_format_source_context(sample_chunks):
    formatted = format_source_context(sample_chunks, token_budget=1000)
    assert "Support Vector Machines" in formatted
    assert "K-Means Clustering" in formatted
    assert "[Chunk " in formatted
    assert "Document: 'Introduction to Machine Learning'" in formatted


def test_find_supporting_chunk(sample_chunks):
    query = "Where are Support Vector Machines explained?"
    found = find_supporting_chunk(query, sample_chunks)
    assert found is not None
    assert found.chunk_id == sample_chunks[0].chunk_id

    ref = build_source_reference(found, "Excerpt test")
    assert ref.chunk_id == found.chunk_id
    assert ref.document_title == "Introduction to Machine Learning"


# =============================================================================
# C8.1: Revision Notes Generator Tests
# =============================================================================

@pytest.mark.asyncio
async def test_revision_note_generator_fallback(sample_chunks):
    """Verifies that deterministic fallback builds complete valid notes without LLM."""
    generator = RevisionNoteGenerator(llm_manager=None)
    req = RevisionNotesGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        length=NoteLength.STANDARD,
        detail_level=DetailLevel.INTERMEDIATE,
        focus=NoteFocus.CONCEPTUAL_LEARNING,
        custom_title="Custom ML Guide",
    )
    note = await generator.generate(sample_chunks, req)

    assert note.title == "Custom ML Guide"
    assert note.length == NoteLength.STANDARD
    assert len(note.sections) >= 1
    assert len(note.source_references) >= 1
    assert "supervised learning" in note.sections[0].summary.lower() or "support vector" in note.sections[0].heading.lower()


@pytest.mark.asyncio
async def test_revision_note_generator_with_mock_llm(sample_chunks):
    """Verifies parsing of structured LLM JSON responses."""
    mock_payload = {
        "title": "Mastering SVM and K-Means",
        "overview": "Synthesized overview of supervised and unsupervised paradigms.",
        "sections": [
            {
                "heading": "Support Vector Machines",
                "summary": "Boundary optimization via hyperplanes.",
                "bullet_points": ["Maximizes margin", "Uses support vectors"],
                "key_takeaways": ["Margin maximization leads to good generalization."],
            }
        ],
        "key_concepts": [
            {"term": "Hyperplane", "definition": "A subspace of dimension p-1.", "context": "Decision boundary"}
        ],
        "important_points": ["SVM operates on linear and non-linear data."],
        "formulas": [
            {"name": "Margin", "expression": "2 / ||w||", "explanation": "Geometric width"}
        ],
        "quick_summary": ["SVM is supervised", "K-Means is unsupervised"],
    }

    mock_provider = MockLLMProvider(default_response=json.dumps(mock_payload))
    manager = LLMManager.get_instance()
    manager.registry.register("mock", mock_provider)

    generator = RevisionNoteGenerator(llm_manager=manager)
    req = RevisionNotesGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        length=NoteLength.DETAILED,
        detail_level=DetailLevel.ADVANCED,
        focus=NoteFocus.TECHNICAL_REFERENCE,
    )
    note = await generator.generate(sample_chunks, req)

    assert note.title == "Mastering SVM and K-Means"
    assert len(note.sections) == 1
    assert note.sections[0].heading == "Support Vector Machines"
    assert len(note.key_concepts) == 1
    assert note.key_concepts[0].term == "Hyperplane"
    assert len(note.formulas) == 1
    assert note.formulas[0].expression == "2 / ||w||"
    assert len(note.source_references) >= 1


# =============================================================================
# C8.2: MCQ Generator Tests
# =============================================================================

@pytest.mark.asyncio
async def test_mcq_generator_fallback(sample_chunks):
    """Verifies deterministic MCQ generation produces valid 4-option single-correct items."""
    generator = MCQGenerator(llm_manager=None)
    req = MCQGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        count=3,
        difficulty=QuestionDifficulty.MEDIUM,
        question_type=MCQType.CONCEPTUAL,
    )
    mcqs = await generator.generate(sample_chunks, req)

    assert len(mcqs) == 3
    for q in mcqs:
        assert len(q.options) == 4
        option_letters = [opt.option_id for opt in q.options]
        assert sorted(option_letters) == ["A", "B", "C", "D"]
        correct_opts = [opt for opt in q.options if opt.is_correct]
        assert len(correct_opts) == 1
        assert correct_opts[0].option_id == q.correct_option_id
        assert len(q.source_references) >= 1


@pytest.mark.asyncio
async def test_mcq_generator_with_mock_llm(sample_chunks):
    """Verifies MCQ generator with parsed LLM responses."""
    mock_mcq_payload = [
        {
            "question_text": "What does K-Means optimize during its iterative assignment step?",
            "difficulty": "medium",
            "question_type": "conceptual",
            "correct_option_id": "C",
            "explanation": "K-Means assigns observations to the cluster with the nearest mean centroid.",
            "topic_tags": ["Clustering", "K-Means"],
            "options": [
                {"option_id": "A", "option_text": "Maximum margin hyperplane", "is_correct": False},
                {"option_id": "B", "option_text": "Cross-entropy loss function", "is_correct": False},
                {"option_id": "C", "option_text": "Distance to the nearest centroid", "is_correct": True},
                {"option_id": "D", "option_text": "Number of dimensions", "is_correct": False},
            ],
        }
    ]

    mock_provider = MockLLMProvider(default_response=json.dumps(mock_mcq_payload))
    manager = LLMManager.get_instance()
    manager.registry.register("mock", mock_provider)

    generator = MCQGenerator(llm_manager=manager)
    req = MCQGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        count=1,
    )
    mcqs = await generator.generate(sample_chunks, req)

    assert len(mcqs) == 1
    q = mcqs[0]
    assert q.correct_option_id == "C"
    assert q.options[2].is_correct is True
    assert q.options[0].is_correct is False
    assert len(q.source_references) >= 1


# =============================================================================
# C8.3: Fill-in-the-Blanks Generator Tests
# =============================================================================

@pytest.mark.asyncio
async def test_fill_blanks_generator_fallback(sample_chunks):
    """Verifies deterministic sentence recall exercise generation."""
    generator = FillBlankGenerator(llm_manager=None)
    req = FillBlankGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        count=2,
        difficulty=QuestionDifficulty.MEDIUM,
    )
    items = await generator.generate(sample_chunks, req)

    assert len(items) == 2
    for item in items:
        assert BLANK_PLACEHOLDER in item.sentence_with_blank
        assert item.canonical_answer in item.original_sentence
        assert item.original_sentence[item.target_start_offset : item.target_end_offset] == item.canonical_answer
        # Reconstruction test
        assert item.sentence_with_blank.replace(BLANK_PLACEHOLDER, item.canonical_answer) == item.original_sentence
        assert item.chunk_id is not None
        assert item.source_reference is not None


@pytest.mark.asyncio
async def test_fill_blanks_generator_with_mock_llm(sample_chunks):
    """Verifies LLM JSON parsing and offset verification."""
    mock_payload = [
        {
            "original_sentence": "Support Vector Machines (SVMs) are supervised learning algorithms used for classification.",
            "sentence_with_blank": "______ (SVMs) are supervised learning algorithms used for classification.",
            "canonical_answer": "Support Vector Machines",
            "accepted_answers": ["SVM", "support vector machines"],
            "target_start_offset": 0,
            "target_end_offset": 23,
            "difficulty": "medium",
            "hint": "A family of maximum-margin classification models.",
            "explanation": "SVMs find maximum-margin boundaries.",
        }
    ]

    mock_provider = MockLLMProvider(default_response=json.dumps(mock_payload))
    manager = LLMManager.get_instance()
    manager.registry.register("mock", mock_provider)

    generator = FillBlankGenerator(llm_manager=manager)
    req = FillBlankGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        count=1,
    )
    items = await generator.generate(sample_chunks, req)

    assert len(items) == 1
    item = items[0]
    assert item.canonical_answer == "Support Vector Machines"
    assert item.target_start_offset == 0
    assert item.target_end_offset == 23
    assert item.original_sentence[item.target_start_offset:item.target_end_offset] == "Support Vector Machines"
    assert item.sentence_with_blank.replace(BLANK_PLACEHOLDER, item.canonical_answer) == item.original_sentence
    assert item.chunk_id == sample_chunks[0].chunk_id


from backend.app.ml.study_materials.flashcard_generator import FlashcardGenerator
from backend.app.ml.study_materials.schemas import (
    FlashcardGenerateRequest,
    FlashcardType,
    TrueFalseGenerateRequest,
)
from backend.app.ml.study_materials.true_false_generator import TrueFalseGenerator


# =============================================================================
# C8.4: True/False Generator Tests
# =============================================================================

@pytest.mark.asyncio
async def test_true_false_generator_fallback(sample_chunks):
    """Verifies deterministic True/False generation with factual inversion."""
    generator = TrueFalseGenerator(llm_manager=None)
    req = TrueFalseGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        count=4,
        target_true_ratio=0.5,
    )
    questions = await generator.generate(sample_chunks, req)

    assert len(questions) == 4
    true_count = sum(1 for q in questions if q.correct_answer is True)
    false_count = sum(1 for q in questions if q.correct_answer is False)

    # Must contain both True and False questions
    assert true_count > 0
    assert false_count > 0

    for q in questions:
        assert len(q.statement) >= 15
        assert isinstance(q.correct_answer, bool)
        assert len(q.explanation) >= 10
        assert q.chunk_id is not None
        assert len(q.source_references) >= 1


@pytest.mark.asyncio
async def test_true_false_generator_with_mock_llm(sample_chunks):
    """Verifies LLM JSON parsing for True/False questions."""
    mock_payload = [
        {
            "statement": "Support Vector Machines find a hyperplane that maximizes the margin.",
            "correct_answer": True,
            "explanation": "SVMs maximize geometric margin between classes.",
            "difficulty": "medium",
            "topic": "Machine Learning",
        },
        {
            "statement": "K-Means is a supervised learning algorithm that requires labeled training sets.",
            "correct_answer": False,
            "explanation": "K-Means is an unsupervised clustering algorithm.",
            "difficulty": "easy",
            "topic": "Clustering",
        },
    ]

    mock_provider = MockLLMProvider(default_response=json.dumps(mock_payload))
    manager = LLMManager.get_instance()
    manager.registry.register("mock", mock_provider)

    generator = TrueFalseGenerator(llm_manager=manager)
    req = TrueFalseGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        count=2,
    )
    questions = await generator.generate(sample_chunks, req)

    assert len(questions) == 2
    assert questions[0].correct_answer is True
    assert questions[1].correct_answer is False
    assert "K-Means" in questions[1].statement


# =============================================================================
# C8.5: Flashcard Generator Tests
# =============================================================================

@pytest.mark.asyncio
async def test_flashcard_generator_fallback(sample_chunks):
    """Verifies deterministic active-recall flashcard synthesis."""
    generator = FlashcardGenerator(llm_manager=None)
    req = FlashcardGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        count=4,
    )
    cards = await generator.generate(sample_chunks, req)

    assert len(cards) == 4
    for card in cards:
        assert 3 <= len(card.front) <= 200
        assert 1 <= len(card.back) <= 500
        assert card.card_type in FlashcardType
        assert card.chunk_id is not None
        assert len(card.source_references) >= 1


@pytest.mark.asyncio
async def test_flashcard_generator_with_mock_llm(sample_chunks):
    """Verifies LLM JSON parsing and notation preservation for flashcards."""
    mock_payload = [
        {
            "front": "What does an SVM maximize?",
            "back": "The geometric margin: 2 / ||w||.",
            "card_type": "concept",
            "difficulty": "medium",
            "topic": "SVM",
        },
        {
            "front": "What is K-Means clustering?",
            "back": "An unsupervised algorithm partitioning n observations into k clusters around centroids.",
            "card_type": "definition",
            "difficulty": "easy",
            "topic": "Clustering",
        },
    ]

    mock_provider = MockLLMProvider(default_response=json.dumps(mock_payload))
    manager = LLMManager.get_instance()
    manager.registry.register("mock", mock_provider)

    generator = FlashcardGenerator(llm_manager=manager)
    req = FlashcardGenerateRequest(
        scope=SourceScope(scope_type=SourceScopeType.WORKSPACE),
        count=2,
    )
    cards = await generator.generate(sample_chunks, req)

    assert len(cards) == 2
    assert cards[0].front == "What does an SVM maximize?"
    assert cards[0].card_type == FlashcardType.CONCEPT
    assert cards[1].card_type == FlashcardType.DEFINITION
