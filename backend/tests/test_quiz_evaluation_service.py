"""Tests for Knovera Quiz Evaluation Service (Phase 8: C8.7)."""

import uuid
from typing import List
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.base import Base
from backend.app.ml.study_materials.evaluation_service import (
    QuizEvaluationService,
    are_answers_equivalent,
    normalize_text_answer,
)
from backend.app.ml.study_materials.schemas import (
    MCQOptionCreate,
    MCQQuestionCreate,
    QuestionDifficulty,
    QuizAttemptAnswerSubmit,
    QuizAttemptStatus,
)
from backend.app.models.study_material import (
    FillBlankExercise,
    MCQOption,
    MCQQuestion,
    QuizAttempt,
    QuizAttemptAnswer,
    TrueFalseQuestion,
)
from backend.app.repositories.study_material_repository import StudyMaterialRepository


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session with static pooling."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_normalize_text_answer():
    """Validates answer text normalization rules."""
    assert normalize_text_answer(None) == ""
    assert normalize_text_answer("   ") == ""
    assert normalize_text_answer("  Hello   World  ") == "hello world"
    # Preserves technical terms and punctuation
    assert normalize_text_answer(" C++  ") == "c++"
    assert normalize_text_answer("Node.js  ") == "node.js"
    assert normalize_text_answer("TF-IDF ") == "tf-idf"
    assert normalize_text_answer("snake_case_var") == "snake_case_var"
    # Unicode NFC normalization
    assert normalize_text_answer("caf\u00e9") == normalize_text_answer("cafe\u0301")


def test_are_answers_equivalent():
    """Validates fuzzy matching and numerical equivalence."""
    # Text exact and case-insensitive
    assert are_answers_equivalent("Photosynthesis", "photosynthesis") is True
    assert are_answers_equivalent(" C++ ", "c++") is True
    assert are_answers_equivalent("Node.js", "node.js") is True

    # Accepted variants
    assert are_answers_equivalent("svm", "Support Vector Machine", ["SVM", "Support Vector Machines"]) is True
    assert are_answers_equivalent("random forest", "Random Forest", ["RF"]) is True

    # Numerical & Decimal equivalence
    assert are_answers_equivalent("0.5", "0.50") is True
    assert are_answers_equivalent("12.0", "12") is True
    assert are_answers_equivalent("3.14159", "3.141590") is True
    assert are_answers_equivalent("0.5", "0.6") is False

    # Negative & Unanswered cases
    assert are_answers_equivalent(None, "target") is False
    assert are_answers_equivalent("", "target") is False
    assert are_answers_equivalent("wrong", "target") is False


def test_quiz_evaluation_service_mcq(db_session: Session):
    """Tests MCQ evaluation in isolation."""
    evaluator = QuizEvaluationService(db_session)
    mcq = MCQQuestion(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        question_text="What does CSS stand for?",
        difficulty="easy",
        correct_option_id="B",
        explanation="Cascading Style Sheets",
        options=[
            MCQOption(id=uuid.uuid4(), option_id="A", option_text="Computer Style Sheets", is_correct=False),
            MCQOption(id=uuid.uuid4(), option_id="B", option_text="Cascading Style Sheets", is_correct=True),
        ],
    )

    # Correct by option id
    is_corr, score, is_unans, expl, val, _ = evaluator.evaluate_mcq(mcq, "B")
    assert is_corr is True
    assert score == 1.0
    assert is_unans is False

    # Correct by full option text
    is_corr, score, is_unans, _, _, _ = evaluator.evaluate_mcq(mcq, "Cascading Style Sheets")
    assert is_corr is True
    assert score == 1.0

    # Incorrect
    is_corr, score, is_unans, _, _, _ = evaluator.evaluate_mcq(mcq, "A")
    assert is_corr is False
    assert score == 0.0

    # Unanswered
    is_corr, score, is_unans, _, _, _ = evaluator.evaluate_mcq(mcq, None)
    assert is_corr is False
    assert score == 0.0
    assert is_unans is True


def test_quiz_evaluation_service_true_false(db_session: Session):
    """Tests True/False statement evaluation."""
    evaluator = QuizEvaluationService(db_session)
    tf = TrueFalseQuestion(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        statement="Python is dynamically typed.",
        difficulty="easy",
        correct_answer=True,
        explanation="Python performs type checking at runtime.",
    )

    # Boolean true
    is_corr, score, is_unans, _, _, _ = evaluator.evaluate_true_false(tf, True)
    assert is_corr is True
    assert score == 1.0

    # String representations
    assert evaluator.evaluate_true_false(tf, "True")[0] is True
    assert evaluator.evaluate_true_false(tf, "true")[0] is True
    assert evaluator.evaluate_true_false(tf, "yes")[0] is True
    assert evaluator.evaluate_true_false(tf, 1)[0] is True

    # Incorrect
    assert evaluator.evaluate_true_false(tf, False)[0] is False
    assert evaluator.evaluate_true_false(tf, "false")[0] is False

    # Unanswered
    is_corr, score, is_unans, _, _, _ = evaluator.evaluate_true_false(tf, None)
    assert is_corr is False
    assert is_unans is True


def test_quiz_evaluation_service_fill_blank(db_session: Session):
    """Tests Fill-in-the-Blank evaluation with canonical and accepted variants."""
    evaluator = QuizEvaluationService(db_session)
    fb = FillBlankExercise(
        id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        sentence_with_blank="_____ is the main memory of a computer.",
        canonical_answer="RAM",
        accepted_answers=["Random Access Memory", "main memory"],
        difficulty="medium",
        explanation="RAM provides high-speed volatile storage.",
    )

    # Canonical match
    assert evaluator.evaluate_fill_blank(fb, "RAM")[0] is True
    assert evaluator.evaluate_fill_blank(fb, "ram")[0] is True
    assert evaluator.evaluate_fill_blank(fb, "  RAM  ")[0] is True

    # Accepted variant
    assert evaluator.evaluate_fill_blank(fb, "Random Access Memory")[0] is True

    # Incorrect
    assert evaluator.evaluate_fill_blank(fb, "ROM")[0] is False

    # Unanswered
    is_corr, _, is_unans, _, _, _ = evaluator.evaluate_fill_blank(fb, "")
    assert is_corr is False
    assert is_unans is True


def test_full_attempt_evaluation_and_idempotency(db_session: Session):
    """Tests multi-question attempt evaluation, summary calculation, and idempotency."""
    ws_id = uuid.uuid4()
    user_id = uuid.uuid4()
    repo = StudyMaterialRepository(db_session)

    # Create questions in DB
    mcq = MCQQuestion(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        question_text="Q1 MCQ",
        difficulty="easy",
        correct_option_id="A",
        explanation="MCQ Explanation",
        is_active=True,
    )
    tf = TrueFalseQuestion(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        statement="Q2 TF",
        difficulty="medium",
        correct_answer=False,
        explanation="TF Explanation",
        is_active=True,
    )
    fb = FillBlankExercise(
        id=uuid.uuid4(),
        workspace_id=ws_id,
        sentence_with_blank="Q3 FB: value is _____.",
        original_sentence="Q3 FB: value is 0.5.",
        canonical_answer="0.5",
        accepted_answers=["1/2", "0.50"],
        difficulty="hard",
        explanation="FB Explanation",
        is_active=True,
    )
    db_session.add_all([mcq, tf, fb])
    db_session.commit()

    # Create active attempt
    attempt = repo.create_quiz_attempt(
        workspace_id=ws_id,
        user_id=user_id,
        title="Comprehensive Unit Test Quiz",
        total_questions=3,
        questions_order=[
            {"id": str(mcq.id), "type": "mcq"},
            {"id": str(tf.id), "type": "true_false"},
            {"id": str(fb.id), "type": "fill_blank"},
        ],
    )

    evaluator = QuizEvaluationService(db_session)

    # Submit answers: MCQ correct ("A"), TF incorrect (True instead of False), FB correct ("0.50" via decimal equivalence)
    answers = [
        QuizAttemptAnswerSubmit(question_id=mcq.id, question_type="mcq", selected_answer="A"),
        QuizAttemptAnswerSubmit(question_id=tf.id, question_type="true_false", selected_answer=True),
        QuizAttemptAnswerSubmit(question_id=fb.id, question_type="fill_blank", selected_answer="0.50"),
    ]

    res = evaluator.evaluate_attempt(attempt=attempt, answers=answers)

    assert res.total_questions == 3
    assert res.correct_count == 2
    assert res.incorrect_count == 1
    assert res.unanswered_count == 0
    assert res.score_percentage == 66.67
    assert res.status == QuizAttemptStatus.EVALUATED
    assert len(res.results) == 3

    # Check immutable results detail
    assert res.results[0].is_correct is True
    assert res.results[1].is_correct is False
    assert res.results[2].is_correct is True

    # Test idempotency: evaluating again returns the same results without error
    db_session.refresh(attempt)
    res2 = evaluator.evaluate_attempt(attempt=attempt)
    assert res2.score_percentage == 66.67
    assert res2.correct_count == 2
