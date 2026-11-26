"""Unit tests for Knovera Study Material Validators (Phase 8 Part 1)."""

import pytest
from backend.app.ml.study_materials.schemas import (
    DetailLevel,
    FillBlankExerciseCreate,
    FormulaItem,
    KeyConceptItem,
    MCQOptionCreate,
    MCQQuestionCreate,
    MCQType,
    NoteFocus,
    NoteLength,
    NoteSection,
    QuestionDifficulty,
    RevisionNoteCreate,
)
from backend.app.ml.study_materials.validators import (
    BLANK_PLACEHOLDER,
    FillBlankValidator,
    MCQValidator,
    RevisionNoteValidator,
)
from backend.app.ml.study_materials.quality_checks import StudyMaterialQualityValidator


def test_revision_note_validator_success():
    note = RevisionNoteCreate(
        title="Support Vector Machines in Machine Learning",
        overview="An overview of maximum-margin classification using hyperplanes.",
        length=NoteLength.STANDARD,
        detail_level=DetailLevel.INTERMEDIATE,
        focus=NoteFocus.CONCEPTUAL_LEARNING,
        sections=[
            NoteSection(
                heading="Optimal Margin Hyperplane",
                summary="SVMs find the decision boundary maximizing the geometric margin.",
                bullet_points=["Margin is 2/||w||", "Support vectors lie on the margin"],
                key_takeaways=["Support vectors alone determine the boundary"],
            )
        ],
        key_concepts=[
            KeyConceptItem(
                term="Support Vector",
                definition="A data point lying directly on the margin boundary.",
            )
        ],
        important_points=["Hyperplanes separate linearly separable classes."],
        formulas=[
            FormulaItem(
                name="Geometric Margin",
                expression="gamma = 2 / ||w||",
                explanation="Distance between positive and negative hyperplanes.",
            )
        ],
        quick_summary=["SVMs maximize margin."],
    )
    passed, errors = RevisionNoteValidator.validate(note)
    assert passed is True
    assert len(errors) == 0

    valid_flag, report = StudyMaterialQualityValidator.validate_revision_note(note)
    assert valid_flag is True
    assert report.total_validated == 1
    assert report.total_rejected == 0


def test_revision_note_validator_failures():
    note = RevisionNoteCreate(
        title="  ",  # whitespace only (<3 chars stripped)
        overview="  short  ",  # whitespace/short (<10 chars stripped)
        sections=[
            NoteSection(heading="   ", summary="   ", bullet_points=[])
        ],
        formulas=[],
    )
    passed, errors = RevisionNoteValidator.validate(note)
    assert passed is False
    assert any("title" in e.lower() for e in errors)
    assert any("overview" in e.lower() for e in errors)
    assert any("heading" in e.lower() for e in errors)


def test_mcq_validator_success():
    mcq = MCQQuestionCreate(
        question_text="What is the primary optimization objective in linear Support Vector Machines?",
        difficulty=QuestionDifficulty.MEDIUM,
        question_type=MCQType.CONCEPTUAL,
        correct_option_id="B",
        explanation="Linear SVMs aim to maximize the geometric margin between classes, which corresponds to minimizing 0.5 * ||w||^2.",
        topic_tags=["Machine Learning", "SVM"],
        options=[
            MCQOptionCreate(option_id="A", option_text="Minimizing the number of data dimensions", is_correct=False),
            MCQOptionCreate(option_id="B", option_text="Maximizing the geometric margin between classes", is_correct=True),
            MCQOptionCreate(option_id="C", option_text="Maximizing the cross-entropy loss function", is_correct=False),
            MCQOptionCreate(option_id="D", option_text="Minimizing tree depth via pruning", is_correct=False),
        ],
    )
    passed, errors = MCQValidator.validate(mcq)
    assert passed is True
    assert len(errors) == 0


def test_mcq_validator_distractor_failures():
    # 1. Banned lazy distractor 'all of the above'
    mcq_lazy = MCQQuestionCreate(
        question_text="Which of the following is true regarding SVM hyperplanes?",
        difficulty=QuestionDifficulty.EASY,
        question_type=MCQType.FACTUAL,
        correct_option_id="D",
        explanation="Testing distractor validation.",
        options=[
            MCQOptionCreate(option_id="A", option_text="They separate data linearly", is_correct=False),
            MCQOptionCreate(option_id="B", option_text="They use kernel tricks", is_correct=False),
            MCQOptionCreate(option_id="C", option_text="They rely on support vectors", is_correct=False),
            MCQOptionCreate(option_id="D", option_text="All of the above", is_correct=True),
        ],
    )
    passed, errors = MCQValidator.validate(mcq_lazy)
    assert passed is False
    assert any("banned lazy distractor" in e for e in errors)


def test_mcq_batch_quality_validator_duplicate_detection():
    mcq1 = MCQQuestionCreate(
        question_text="What is the capital of France?",
        difficulty=QuestionDifficulty.EASY,
        question_type=MCQType.FACTUAL,
        correct_option_id="A",
        explanation="Paris is the capital of France.",
        options=[
            MCQOptionCreate(option_id="A", option_text="Paris", is_correct=True),
            MCQOptionCreate(option_id="B", option_text="London", is_correct=False),
            MCQOptionCreate(option_id="C", option_text="Berlin", is_correct=False),
            MCQOptionCreate(option_id="D", option_text="Madrid", is_correct=False),
        ],
    )
    mcq2 = mcq1.model_copy()  # exact duplicate stem

    valid_items, report = StudyMaterialQualityValidator.validate_mcq_batch([mcq1, mcq2], total_requested=2)
    assert len(valid_items) == 1
    assert report.total_validated == 1
    assert report.total_rejected == 1
    assert any("duplicate" in r.lower() for r in report.rejection_reasons)


def test_fill_blank_validator_and_reconstruction():
    orig = "Support Vector Machines find an optimal hyperplane separating data classes."
    ans = "Support Vector Machines"
    start_idx = orig.find(ans)
    end_idx = start_idx + len(ans)

    exercise = FillBlankExerciseCreate(
        original_sentence=orig,
        sentence_with_blank=f"{BLANK_PLACEHOLDER} find an optimal hyperplane separating data classes.",
        canonical_answer=ans,
        accepted_answers=["SVM", "Support Vector Machines"],
        target_start_offset=start_idx,
        target_end_offset=end_idx,
        difficulty=QuestionDifficulty.MEDIUM,
        hint="A maximum-margin supervised learning classification model.",
        explanation="SVMs construct hyperplanes in high-dimensional space.",
    )

    passed, errors, repaired = FillBlankValidator.validate_and_repair(exercise)
    assert passed is True
    assert len(errors) == 0
    assert repaired.target_start_offset == 0
    assert repaired.target_end_offset == 23
    # Sentence reconstruction check
    assert repaired.sentence_with_blank.replace(BLANK_PLACEHOLDER, repaired.canonical_answer) == orig


def test_fill_blank_offset_auto_repair():
    orig = "TF-IDF assigns higher numerical weights to rare discriminative terms."
    ans = "TF-IDF"

    # Deliberately supply wrong character offsets
    exercise = FillBlankExerciseCreate(
        original_sentence=orig,
        sentence_with_blank=f"{BLANK_PLACEHOLDER} assigns higher numerical weights to rare discriminative terms.",
        canonical_answer=ans,
        accepted_answers=["tfidf"],
        target_start_offset=10,  # Incorrect!
        target_end_offset=16,    # Incorrect!
        difficulty=QuestionDifficulty.EASY,
        hint="A frequency-based feature weighting statistic.",
    )

    passed, errors, repaired = FillBlankValidator.validate_and_repair(exercise)
    assert passed is True
    # Offsets should be repaired to 0 and 6
    assert repaired.target_start_offset == 0
    assert repaired.target_end_offset == 6
    assert orig[repaired.target_start_offset:repaired.target_end_offset] == "TF-IDF"


def test_fill_blank_hint_leak_detection():
    orig = "Logistic Regression calculates probabilities via the sigmoid function."
    ans = "Logistic Regression"

    exercise = FillBlankExerciseCreate(
        original_sentence=orig,
        sentence_with_blank=f"{BLANK_PLACEHOLDER} calculates probabilities via the sigmoid function.",
        canonical_answer=ans,
        accepted_answers=[],
        target_start_offset=0,
        target_end_offset=len(ans),
        difficulty=QuestionDifficulty.EASY,
        hint="Think about Logistic Regression and its sigmoid curve.",  # Leaks answer!
    )

    passed, errors, _ = FillBlankValidator.validate_and_repair(exercise)
    assert passed is False
    assert any("hint leaks" in e.lower() for e in errors)


from backend.app.ml.study_materials.schemas import (
    FlashcardCreate,
    FlashcardType,
    TrueFalseQuestionCreate,
    ValidationStatus,
)
from backend.app.ml.study_materials.validators import (
    FlashcardValidator,
    TrueFalseValidator,
)


def test_true_false_validator_success():
    # Valid True statement
    q_true = TrueFalseQuestionCreate(
        statement="Support Vector Machines aim to maximize the geometric margin between classes.",
        correct_answer=True,
        explanation="Linear SVM finds the hyperplanes with maximum geometric distance from support vectors.",
        difficulty=QuestionDifficulty.MEDIUM,
        topic="Machine Learning",
    )
    passed, errors = TrueFalseValidator.validate(q_true)
    assert passed is True
    assert len(errors) == 0

    # Valid False statement
    q_false = TrueFalseQuestionCreate(
        statement="K-Means clustering is a supervised classification technique that requires labeled training instances.",
        correct_answer=False,
        explanation="K-Means is an unsupervised clustering algorithm that partitions unlabeled data points into K clusters.",
        difficulty=QuestionDifficulty.EASY,
        topic="Machine Learning",
    )
    passed, errors = TrueFalseValidator.validate(q_false)
    assert passed is True
    assert len(errors) == 0


def test_true_false_validator_failures():
    # Statement too short (<15 chars)
    q_short = TrueFalseQuestionCreate(
        statement="SVM good.",
        correct_answer=True,
        explanation="SVM is a strong classifier.",
        difficulty=QuestionDifficulty.EASY,
    )
    passed, errors = TrueFalseValidator.validate(q_short)
    assert passed is False
    assert any("too short" in e.lower() for e in errors)

    # Double negative statement
    q_double_neg = TrueFalseQuestionCreate(
        statement="It is not impossible that deep neural nets cannot never overfit.",
        correct_answer=False,
        explanation="Models can overfit during prolonged training.",
        difficulty=QuestionDifficulty.HARD,
    )
    passed, errors = TrueFalseValidator.validate(q_double_neg)
    assert passed is False
    assert any("double negative" in e.lower() for e in errors)

    # False question missing explanation (<10 chars)
    q_no_exp = TrueFalseQuestionCreate(
        statement="Linear regression can only output discrete categorical class labels.",
        correct_answer=False,
        explanation="brief",  # 5 chars passes pydantic min_length, but <10 in domain validator
        difficulty=QuestionDifficulty.MEDIUM,
    )
    passed, errors = TrueFalseValidator.validate(q_no_exp)
    assert passed is False
    assert any("explanation" in e.lower() for e in errors)


def test_flashcard_validator_success():
    fc = FlashcardCreate(
        front="What is the geometric margin in Support Vector Machines?",
        back="The shortest Euclidean distance between the decision boundary hyperplane and any training sample.",
        card_type=FlashcardType.DEFINITION,
        difficulty=QuestionDifficulty.MEDIUM,
        topic="Machine Learning",
    )
    passed, errors = FlashcardValidator.validate(fc)
    assert passed is True
    assert len(errors) == 0


def test_flashcard_validator_failures():
    # Front too long (>200 chars) bypassing pydantic via model_construct
    long_front = "A" * 250
    fc_long = FlashcardCreate.model_construct(
        front=long_front,
        back="Valid concise answer.",
        card_type=FlashcardType.CONCEPT,
        difficulty=QuestionDifficulty.HARD,
    )
    passed, errors = FlashcardValidator.validate(fc_long)
    assert passed is False
    assert any("front exceeds" in e.lower() for e in errors)

    # Front echoes back
    fc_echo = FlashcardCreate(
        front="Gradient Descent",
        back="Gradient Descent",
        card_type=FlashcardType.TERMINOLOGY,
        difficulty=QuestionDifficulty.EASY,
    )
    passed, errors = FlashcardValidator.validate(fc_echo)
    assert passed is False
    assert any("echoes" in e.lower() for e in errors)


def test_batch_quality_checks_true_false_and_flashcards():
    valid_tfs = [
        TrueFalseQuestionCreate(
            statement=f"Document statement {i} describes clear algorithmic principles in data science.",
            correct_answer=(i % 2 == 0),
            explanation=f"Detailed justification explaining the factual basis for item {i}.",
            difficulty=QuestionDifficulty.MEDIUM,
        )
        for i in range(4)
    ]
    # Add an invalid one
    invalid_tf = TrueFalseQuestionCreate(
        statement="Short stmt.",
        correct_answer=True,
        explanation="Valid explanation of sufficient length.",
        difficulty=QuestionDifficulty.EASY,
    )
    valid_batch, report = StudyMaterialQualityValidator.validate_true_false_batch(
        valid_tfs + [invalid_tf],
        total_requested=5,
    )
    assert len(valid_batch) == 4
    assert report.total_rejected >= 1

    valid_fcs = [
        FlashcardCreate(
            front=f"Term {i} concept",
            back=f"Explanation for term {i}",
            card_type=FlashcardType.CONCEPT,
            difficulty=QuestionDifficulty.EASY,
        )
        for i in range(4)
    ]
    invalid_fc = FlashcardCreate.model_construct(
        front="X" * 250,
        back="Valid back",
        card_type=FlashcardType.CONCEPT,
    )
    valid_fc_batch, fc_report = StudyMaterialQualityValidator.validate_flashcards_batch(
        valid_fcs + [invalid_fc],
        total_requested=5,
    )
    assert len(valid_fc_batch) == 4
    assert fc_report.total_rejected >= 1
