"""Versioned, injection-safe prompts for Knovera Study Material Generation.

Provides structured prompt templates enforcing:
- JSON object output conformance with response_format="json_object"
- Anti-injection context boundaries (<source_context> ... </source_context>)
- Strict negative constraints against slide banners, course codes, and institutional noise
- Distractor plausibility for MCQs
- Offset and exact sentence preservation for Fill-in-the-Blanks
- Factually balanced True/False statements with targeted misconception correction
- High-yield, concise front/back Flashcard recall prompts
"""

from typing import List, Optional
from backend.app.ml.study_materials.schemas import (
    DetailLevel,
    FlashcardType,
    MCQType,
    NoteFocus,
    NoteLength,
    QuestionDifficulty,
)

REVISION_NOTES_PROMPT_VERSION = "revision-notes-v2"
MCQ_PROMPT_VERSION = "mcq-generator-v2"
FILL_BLANKS_PROMPT_VERSION = "fill-blanks-v2"
TRUE_FALSE_PROMPT_VERSION = "true-false-v2"
FLASHCARDS_PROMPT_VERSION = "flashcards-v2"


def build_revision_notes_prompt(
    context_text: str,
    length: NoteLength = NoteLength.STANDARD,
    detail_level: DetailLevel = DetailLevel.INTERMEDIATE,
    focus: NoteFocus = NoteFocus.CONCEPTUAL_LEARNING,
    custom_title: Optional[str] = None,
) -> str:
    """Builds prompt for generating structured, source-grounded revision notes."""
    focus_guidance = {
        NoteFocus.EXAM_REVISION: "Prioritize high-yield exam takeaways, critical definitions, quick recall points, and common traps.",
        NoteFocus.CONCEPTUAL_LEARNING: "Emphasize foundational intuition, mental models, how core principles connect, and illustrative analogies.",
        NoteFocus.TECHNICAL_REFERENCE: "Focus on formal definitions, algorithm steps, mathematical expressions, code/system logic, and constraints.",
        NoteFocus.RESEARCH_REVIEW: "Highlight methodologies, problem formulations, empirical findings, comparative advantages, and open research questions.",
    }.get(focus, "Provide a balanced, structured synthesis of the content.")

    length_guidance = {
        NoteLength.CONCISE: "Generate a compact 2-3 section summary focusing only on essential highlights.",
        NoteLength.STANDARD: "Generate a comprehensive 3-5 section review with thorough coverage of key topics.",
        NoteLength.DETAILED: "Generate an exhaustive deep-dive with 5+ sections, in-depth breakdowns, and thorough conceptual explanations.",
    }.get(length, "Provide standard depth.")

    title_clause = f'Use the title: "{custom_title}".' if custom_title else "Generate an appropriate academic title reflecting the material."

    return (
        f"You are an expert academic tutor and study material designer for Knovera.\n"
        f"Task: Generate comprehensive, highly structured revision notes from the provided verified source material.\n\n"
        f"Requirements:\n"
        f"- {title_clause}\n"
        f"- Length: {length.value} ({length_guidance})\n"
        f"- Detail Level: {detail_level.value} (target tone and depth accordingly)\n"
        f"- Focus Style: {focus.value} ({focus_guidance})\n"
        f"- Grounding: Every concept, definition, and formula must be explicitly supported by the text. NEVER hallucinate formulas or technical facts not in the source.\n"
        f"- Negative Constraints: NEVER include slide watermarks, university names (e.g. JIIT, CSE&IT), course codes, or lecturer signatures.\n\n"
        f"Return ONLY a valid JSON object matching this schema:\n"
        f"{{\n"
        f'  "title": "Document / Study Topic Title",\n'
        f'  "overview": "Comprehensive high-level summary of the covered topic and core goals",\n'
        f'  "sections": [\n'
        f"    {{\n"
        f'      "heading": "Section Heading (e.g. Problem Formulation, Algorithmic Steps, Trade-offs)",\n'
        f'      "summary": "Thorough section overview explaining core ideas",\n'
        f'      "bullet_points": ["Detailed technical point 1", "Detailed technical point 2", "Detailed technical point 3"],\n'
        f'      "key_takeaways": ["Critical takeaway 1", "Critical takeaway 2"]\n'
        f"    }}\n"
        f"  ],\n"
        f'  "key_concepts": [\n'
        f'    {{"term": "Concept Name", "definition": "Clear, precise academic definition", "context": "Usage context and significance"}}\n'
        f"  ],\n"
        f'  "important_points": ["Critical fact or rule 1", "Common confusion or trap to avoid 2"],\n'
        f'  "formulas": [\n'
        f'    {{"name": "Equation or Formula Name", "expression": "LaTeX or text formula", "explanation": "Variable definitions and meaning"}}\n'
        f"  ],\n"
        f'  "quick_summary": ["High-yield summary takeaway 1", "High-yield summary takeaway 2", "High-yield summary takeaway 3"]\n'
        f"}}\n\n"
        f"<source_context>\n"
        f"{context_text}\n"
        f"</source_context>\n"
    )


def build_mcq_prompt(
    context_text: str,
    count: int = 5,
    difficulty: Optional[QuestionDifficulty] = None,
    question_type: Optional[MCQType] = None,
) -> str:
    """Builds prompt for generating multiple-choice questions with 4 distinct options."""
    diff_instruction = f"Target difficulty: {difficulty.value}." if difficulty else "Vary difficulty across easy, medium, and hard."
    type_instruction = f"Focus on question type: {question_type.value}." if question_type else "Cover conceptual, factual, and application questions."

    return (
        f"You are an assessment author for Knovera. Generate exactly {count} high-quality Multiple-Choice Questions (MCQs) based STRICTLY on the source text.\n\n"
        f"Rules for MCQs:\n"
        f"1. Exactly 4 options per question: 'A', 'B', 'C', and 'D'.\n"
        f"2. Exactly ONE correct option. The remaining 3 must be plausible distractors reflecting common student misconceptions.\n"
        f"3. NEVER use lazy distractors like 'All of the above', 'None of the above', or 'Both A and B'.\n"
        f"4. Randomize the position of the correct answer across A, B, C, and D.\n"
        f"5. Difficulty: {diff_instruction}\n"
        f"6. Type: {type_instruction}\n"
        f"7. Explanation: Explain why the correct answer is true AND why key distractors are false.\n"
        f"8. Grounding: All questions must be answerable purely from the provided source text.\n"
        f"9. STRICT NEGATIVE CONSTRAINTS:\n"
        f"   - NEVER include document filenames, lecture numbers (e.g. 'Lecture-11'), slide numbers, course codes (e.g. '9M12CS112'), or university/department names (e.g. 'JIIT', 'CSE&IT', 'NOIDA').\n"
        f"   - Stems must be clean, complete grammatical sentences testing domain principles only.\n\n"
        f"Return ONLY a valid JSON object matching this schema:\n"
        f"{{\n"
        f'  "questions": [\n'
        f"    {{\n"
        f'      "question_text": "Clear, grammatically complete question stem?",\n'
        f'      "difficulty": "easy | medium | hard",\n'
        f'      "question_type": "conceptual | factual | application | comparison | analytical_reasoning",\n'
        f'      "correct_option_id": "A | B | C | D",\n'
        f'      "explanation": "Detailed explanation of why correct option is true and others are false",\n'
        f'      "topic_tags": ["domain_concept1", "domain_concept2"],\n'
        f'      "options": [\n'
        f'        {{"option_id": "A", "option_text": "Text for option A", "is_correct": true}},\n'
        f'        {{"option_id": "B", "option_text": "Text for option B", "is_correct": false}},\n'
        f'        {{"option_id": "C", "option_text": "Text for option C", "is_correct": false}},\n'
        f'        {{"option_id": "D", "option_text": "Text for option D", "is_correct": false}}\n'
        f"      ]\n"
        f"    }}\n"
        f"  ]\n"
        f"}}\n\n"
        f"<source_context>\n"
        f"{context_text}\n"
        f"</source_context>\n"
    )


def build_fill_blanks_prompt(
    context_text: str,
    count: int = 5,
    difficulty: Optional[QuestionDifficulty] = None,
) -> str:
    """Builds prompt for generating fill-in-the-blank recall exercises."""
    diff_instruction = f"Target difficulty: {difficulty.value}." if difficulty else "Provide an appropriate mix of difficulty levels."

    return (
        f"You are a pedagogical assessment designer for Knovera. Generate exactly {count} Fill-in-the-Blank recall exercises based STRICTLY on the source text.\n\n"
        f"Strict Requirements:\n"
        f"1. Choose a factual, unambiguous, complete sentence taken from the source context.\n"
        f"2. Select a single high-value technical term, algorithm, definition, or domain concept to blank out.\n"
        f"3. In 'sentence_with_blank', replace the exact selected term with exactly six underscores: '______'.\n"
        f"4. 'canonical_answer' must be the exact substring removed.\n"
        f"5. The sentence must be fully reconstructible: original_sentence.replace(canonical_answer, '______', 1) == sentence_with_blank.\n"
        f"6. 'accepted_answers': include lowercase/uppercase variations, acronyms, or verified synonyms.\n"
        f"7. 'target_start_offset' and 'target_end_offset': 0-based character start and end index of canonical_answer inside original_sentence.\n"
        f"8. 'hint': provide a helpful category or semantic hint that DOES NOT spell out the answer.\n"
        f"9. Difficulty: {diff_instruction}\n"
        f"10. STRICT NEGATIVE CONSTRAINTS:\n"
        f"    - NEVER blank out or include slide headers, course codes, institutional names (e.g. 'JIIT', 'CSE&IT', 'NOIDA'), or lecturer names.\n"
        f"    - NEVER use broken sentence fragments (such as starting with 'of ' or containing slide markers).\n\n"
        f"Return ONLY a valid JSON object matching this schema:\n"
        f"{{\n"
        f'  "questions": [\n'
        f"    {{\n"
        f'      "original_sentence": "Support Vector Machines find an optimal hyperplane separating data points.",\n'
        f'      "sentence_with_blank": "______ find an optimal hyperplane separating data points.",\n'
        f'      "canonical_answer": "Support Vector Machines",\n'
        f'      "accepted_answers": ["SVM", "SVMs", "support vector machines"],\n'
        f'      "target_start_offset": 0,\n'
        f'      "target_end_offset": 23,\n'
        f'      "difficulty": "medium",\n'
        f'      "hint": "A supervised machine learning classification algorithm based on maximum margin hyperplanes.",\n'
        f'      "explanation": "Support Vector Machines (SVMs) aim to find a hyperplane that maximizes the margin between classes."\n'
        f"    }}\n"
        f"  ]\n"
        f"}}\n\n"
        f"<source_context>\n"
        f"{context_text}\n"
        f"</source_context>\n"
    )


def build_true_false_prompt(
    context_text: str,
    count: int = 5,
    difficulty: Optional[QuestionDifficulty] = None,
    target_true_ratio: float = 0.5,
) -> str:
    """Builds prompt for generating source-grounded True/False questions."""
    diff_instruction = f"Target difficulty: {difficulty.value}." if difficulty else "Vary difficulty across easy (30%), medium (50%), and hard (20%)."
    num_true = round(count * target_true_ratio)
    num_false = count - num_true

    return (
        f"You are an assessment specialist for Knovera. Generate exactly {count} source-grounded True/False assessment questions based STRICTLY on the source text.\n\n"
        f"Distribution Target:\n"
        f"- Target approximately {num_true} TRUE statement(s) and {num_false} FALSE statement(s).\n"
        f"- {diff_instruction}\n\n"
        f"Quality Rules:\n"
        f"1. Complete declarative statement: Write a single, focused, unambiguous declarative sentence ending with a period.\n"
        f"2. Single core concept: Test exactly one primary knowledge point or relationship per question.\n"
        f"3. Strict True rules: True statements must be directly and independently verifiable from the source context.\n"
        f"4. Plausible False misconceptions: False statements MUST introduce a plausible, common misconception or specific factual inversion (e.g. swapping an algorithm property, condition, or role). Never make a sentence false through random gibberish.\n"
        f"5. Explanations: For True statements, cite the verified source principle. For False statements, explicitly identify the incorrect error and state the supported correction.\n"
        f"6. STRICT NEGATIVE CONSTRAINTS:\n"
        f"   - NEVER generate statements from slide titles, lecture numbers (e.g. 'Lecture-11'), course codes ('9M12CS112'), university affiliations ('JIIT', 'CSE&IT', 'NOIDA'), or lecturer names.\n"
        f"   - NEVER use dangling fragments (e.g. starting with 'of ', 'does not ', or bullet characters '•'). Every statement must be a complete, self-contained English sentence.\n\n"
        f"Return ONLY a valid JSON object matching this schema:\n"
        f"{{\n"
        f'  "questions": [\n'
        f"    {{\n"
        f'      "statement": "K-Means uses an iterative optimization process to minimize within-cluster sum of squares.",\n'
        f'      "correct_answer": true,\n'
        f'      "explanation": "K-Means iteratively reassigns samples to nearest centroids and updates centroids to minimize the within-cluster sum of squares.",\n'
        f'      "difficulty": "medium",\n'
        f'      "topic": "Clustering Algorithms"\n'
        f"    }}\n"
        f"  ]\n"
        f"}}\n\n"
        f"<source_context>\n"
        f"{context_text}\n"
        f"</source_context>\n"
    )


def build_flashcards_prompt(
    context_text: str,
    count: int = 10,
    difficulty: Optional[QuestionDifficulty] = None,
    card_type: Optional[FlashcardType] = None,
) -> str:
    """Builds prompt for generating high-yield recall flashcards."""
    diff_instruction = f"Target difficulty: {difficulty.value}." if difficulty else "Provide an appropriate mix of difficulty levels."
    type_instruction = f"Focus exclusively on card type: {card_type.value}." if card_type else "Cover diverse card types: definition, concept, fact, formula, algorithm, comparison, application, terminology."

    return (
        f"You are an active-recall cognitive learning expert for Knovera. Generate exactly {count} high-yield study flashcards based STRICTLY on the source text.\n\n"
        f"Instructions:\n"
        f"- {diff_instruction}\n"
        f"- {type_instruction}\n"
        f"- Breadth of coverage: Distribute cards across the entire source context rather than concentrating only on the first paragraph.\n"
        f"- Negative Constraints: Never include slide headers, course codes, institutional names (JIIT, CSE&IT), or lecturer names.\n\n"
        f"Card Quality Rules:\n"
        f"1. Front: Ask one clear question or present one concise recall prompt (~5-10 words, ~80 characters, max 120 characters).\n"
        f"2. Back: Provide the precise, factual answer with sufficient context to be unambiguous (~5-10 words, ~80 characters).\n"
        f"3. Formulas & Algorithms: Preserve mathematical notation and exact technical terminology.\n"
        f"4. Distinct recall target: Each card must test exactly one primary concept without trailing sub-questions.\n\n"
        f"Return ONLY a valid JSON object matching this schema:\n"
        f"{{\n"
        f'  "flashcards": [\n'
        f"    {{\n"
        f'      "front": "What is the primary optimization objective in linear Support Vector Machines?",\n'
        f'      "back": "Maximize the geometric margin separating class boundaries.",\n'
        f'      "card_type": "concept",\n'
        f'      "difficulty": "medium",\n'
        f'      "topic": "Support Vector Machines"\n'
        f"    }}\n"
        f"  ]\n"
        f"}}\n\n"
        f"<source_context>\n"
        f"{context_text}\n"
        f"</source_context>\n"
    )
