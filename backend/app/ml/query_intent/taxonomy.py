"""Query Intent Taxonomy Registry and Annotation Rules for Knovera (Phase 5 C5.1).

Centralized authoritative source for query intent categories, multi-intent
priority ordering, auxiliary query attributes, and taxonomy validation.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

TAXONOMY_VERSION: str = "1.0.0"


class IntentCategoryEnum(str, Enum):
    """Enumeration of all 13 supported primary query intent categories."""

    FACTUAL_LOOKUP = "factual_lookup"
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    COMPARISON = "comparison"
    SUMMARIZATION = "summarization"
    PROCEDURAL_GUIDANCE = "procedural_guidance"
    ANALYTICAL_REASONING = "analytical_reasoning"
    INFORMATION_EXTRACTION = "information_extraction"
    SOURCE_EVIDENCE = "source_evidence"
    RECOMMENDATION = "recommendation"
    GENERAL_CONVERSATION = "general_conversation"
    UNSUPPORTED_ACTION = "unsupported_action"
    AMBIGUOUS = "ambiguous"


class AuxiliaryQueryAttributes(BaseModel):
    """Auxiliary characteristics describing query complexity independently of primary intent."""

    requires_conversation_context: bool = Field(
        default=False,
        description="Whether answering requires context from previous conversation turns.",
    )
    requires_multi_source_evidence: bool = Field(
        default=False,
        description="Whether resolving the query demands synthesizing across multiple distinct documents.",
    )
    requests_explicit_citations: bool = Field(
        default=False,
        description="Whether the user explicitly requests citations, quotations, or page references.",
    )
    contains_ambiguous_reference: bool = Field(
        default=False,
        description="Whether the query contains unresolved anaphora or deictic pronouns (e.g. 'that one', 'the second one').",
    )


class IntentCategory(BaseModel):
    """Specification of a single query intent category in the taxonomy."""

    id: str
    name: str
    description: str
    inclusion_rules: List[str]
    exclusion_rules: List[str]
    positive_examples: List[str]
    borderline_examples: List[str]
    annotation_guidance: str


# Explicit Precedence Hierarchy for Multi-Intent Disambiguation (Prompt Section 3.5)
# When a query contains overlapping task cues, resolve using this dominant task precedence:
MULTI_INTENT_PRECEDENCE: List[str] = [
    IntentCategoryEnum.SOURCE_EVIDENCE.value,
    IntentCategoryEnum.COMPARISON.value,
    IntentCategoryEnum.SUMMARIZATION.value,
    IntentCategoryEnum.RECOMMENDATION.value,
    IntentCategoryEnum.INFORMATION_EXTRACTION.value,
    IntentCategoryEnum.PROCEDURAL_GUIDANCE.value,
    IntentCategoryEnum.ANALYTICAL_REASONING.value,
    IntentCategoryEnum.DEFINITION.value,
    IntentCategoryEnum.EXPLANATION.value,
    IntentCategoryEnum.FACTUAL_LOOKUP.value,
]

# Operational Categories (evaluated by definition rather than task hierarchy)
OPERATIONAL_CATEGORIES: List[str] = [
    IntentCategoryEnum.GENERAL_CONVERSATION.value,
    IntentCategoryEnum.UNSUPPORTED_ACTION.value,
    IntentCategoryEnum.AMBIGUOUS.value,
]


_INTENT_DEFINITIONS: Dict[str, IntentCategory] = {
    IntentCategoryEnum.FACTUAL_LOOKUP.value: IntentCategory(
        id=IntentCategoryEnum.FACTUAL_LOOKUP.value,
        name="Factual Lookup",
        description="The user seeks a specific, concrete piece of factual information, date, number, entity, or isolated finding from the documents.",
        inclusion_rules=[
            "Direct questions seeking dates, numbers, authors, names, or reported metrics.",
            "Queries answerable with a single bounded fact or data point from a source.",
        ],
        exclusion_rules=[
            "Do not use if the query asks for a list or structured compilation (use information_extraction).",
            "Do not use if the query asks for the mechanism of how or why something occurred (use explanation).",
            "Do not use if the query explicitly asks for source locations or page citations (use source_evidence).",
        ],
        positive_examples=[
            "When was the company founded?",
            "What is the population mentioned in the report?",
            "Which algorithm does the document use?",
            "What is the reported accuracy on ImageNet?",
            "Who are the co-authors of the paper?",
        ],
        borderline_examples=[
            "What are the numbers reported in table 2? -> information_extraction (requesting extraction of structured data).",
            "Why did the company change its founding date? -> explanation (asking for causal reasoning).",
        ],
        annotation_guidance="Apply when the target response is a discrete factual answer without requiring synthesis, step-by-step procedures, or conceptual elaboration.",
    ),
    IntentCategoryEnum.DEFINITION.value: IntentCategory(
        id=IntentCategoryEnum.DEFINITION.value,
        name="Definition",
        description="The user asks for the concise definition, meaning, or expansion of a concept, term, acronym, or technical expression.",
        inclusion_rules=[
            "Queries asking 'What is X?', 'Define X', 'What does X stand for?', or 'Explain the meaning of X'.",
            "Queries targeting terminological clarification rather than full operational mechanisms.",
        ],
        exclusion_rules=[
            "Do not use if the user asks for a comprehensive explanation of how an algorithm works (use explanation).",
            "Do not use if the user asks for comparative differences between two defined terms (use comparison).",
        ],
        positive_examples=[
            "What is machine learning?",
            "Define BM25.",
            "What does RAG mean?",
            "Explain the meaning of entropy.",
            "What is a cross-encoder in NLP?",
        ],
        borderline_examples=[
            "Explain how BM25 scores passages. -> explanation (asking for algorithmic mechanics rather than just definition).",
            "What is the difference between RAG and fine-tuning? -> comparison (explicit dual-concept contrast).",
        ],
        annotation_guidance="Distinguish brief definitional inquiries from in-depth mechanistic explanations. If the query asks for how something functions or operates under the hood, prefer explanation.",
    ),
    IntentCategoryEnum.EXPLANATION.value: IntentCategory(
        id=IntentCategoryEnum.EXPLANATION.value,
        name="Explanation",
        description="The user seeks to understand how, why, or under what mechanisms a concept, algorithm, phenomenon, or theory operates.",
        inclusion_rules=[
            "Queries asking 'How does X work?', 'Why does Y happen?', or 'Explain the mechanism of Z'.",
            "Conceptual and mechanistic walkthroughs requiring deeper reasoning than a dictionary definition.",
        ],
        exclusion_rules=[
            "Do not use if the query explicitly compares two entities or methods (use comparison).",
            "Do not use if the query asks for actionable implementation steps or code commands (use procedural_guidance).",
            "Do not use if the query asks for evaluation or deduction based on empirical evidence (use analytical_reasoning).",
        ],
        positive_examples=[
            "How does gradient descent work?",
            "Why does overfitting occur in deep networks?",
            "Explain how a transformer self-attention layer learns.",
            "Why is layer normalization required in transformers?",
            "How does Raft consensus elect a leader?",
        ],
        borderline_examples=[
            "Explain how to implement gradient descent in PyTorch. -> procedural_guidance (requesting implementation steps).",
            "Explain why model A outperformed model B in the experiment. -> analytical_reasoning (deductive evaluation of results).",
        ],
        annotation_guidance="Focus on mechanistic and conceptual 'how/why' understanding. When words like 'explain' are paired with comparative or procedural terms, the dominant task overrides.",
    ),
    IntentCategoryEnum.COMPARISON.value: IntentCategory(
        id=IntentCategoryEnum.COMPARISON.value,
        name="Comparison",
        description="The user wants to compare, contrast, or differentiate two or more concepts, algorithms, frameworks, methodologies, or documents.",
        inclusion_rules=[
            "Queries contrasting two or more subjects ('Compare X and Y', 'Differences between A and B').",
            "Queries evaluating trade-offs, pros/cons, or relative suitability between options.",
        ],
        exclusion_rules=[
            "Do not use if only a single concept is discussed without an explicit or implied comparative counterpart.",
            "Do not use if the query asks for a single recommendation without comparative analysis (use recommendation).",
        ],
        positive_examples=[
            "Compare TCP and UDP protocols.",
            "What is the difference between TF-IDF and BM25?",
            "Compare the experimental methodologies used in these two papers.",
            "How does PyTorch differ from TensorFlow in graph execution?",
            "Contrast B-Trees and LSM-Trees for write-heavy workloads.",
        ],
        borderline_examples=[
            "Explain the difference between TCP and UDP. -> comparison (presence of 'explain' does not override comparison precedence).",
            "Which is better, TCP or UDP, for streaming audio? -> recommendation (user is asking for a decision/selection recommendation).",
        ],
        annotation_guidance="Take precedence over 'explanation' and 'definition' whenever multiple entities are juxtaposed for contrast.",
    ),
    IntentCategoryEnum.SUMMARIZATION.value: IntentCategory(
        id=IntentCategoryEnum.SUMMARIZATION.value,
        name="Summarization",
        description="The user asks for a condensed synthesis, high-level overview, executive summary, or key takeaways of an entire document, chapter, or workspace collection.",
        inclusion_rules=[
            "Explicit requests for summary, abstract, overview, or main takeaways of a body of text.",
            "Requests for synthesizing broad findings across sections or documents.",
        ],
        exclusion_rules=[
            "Do not use if the user asks for a specific isolated fact from the summary (use factual_lookup).",
            "Do not use if the user asks to extract specific items like entities or tables (use information_extraction).",
        ],
        positive_examples=[
            "Summarize this research paper.",
            "Give me the key findings of this chapter.",
            "Summarize all documents in this workspace.",
            "Provide an executive summary of the project proposal.",
            "Give me a short overview of the methodology section.",
        ],
        borderline_examples=[
            "List the main contributions of this paper. -> information_extraction (requesting extraction of discrete items).",
            "Evaluate whether the summary accurately reflects the data. -> analytical_reasoning (evaluative task).",
        ],
        annotation_guidance="Summarization targets comprehensive condensation of multi-paragraph or multi-page documents rather than focused information lookup.",
    ),
    IntentCategoryEnum.PROCEDURAL_GUIDANCE.value: IntentCategory(
        id=IntentCategoryEnum.PROCEDURAL_GUIDANCE.value,
        name="Procedural Guidance",
        description="The user seeks actionable instructions, step-by-step methods, configuration walkthroughs, or procedural recipes to achieve a task.",
        inclusion_rules=[
            "Queries asking 'How do I...', 'Steps to configure...', 'Guide me through...', or 'How can I implement...'.",
            "Procedural instructions, operational steps, or ordered workflows.",
        ],
        exclusion_rules=[
            "Do not use if the query asks why a procedure works theoretically (use explanation).",
            "Do not use if the query asks Knovera to execute an unsupported external action (use unsupported_action).",
        ],
        positive_examples=[
            "How do I implement K-Means clustering in Python?",
            "List the steps involved in the experimental procedure.",
            "How can I configure PostgreSQL connection pooling in FastAPI?",
            "Explain the step-by-step process of fine-tuning the model.",
            "What are the commands to run the database migrations?",
        ],
        borderline_examples=[
            "How does K-Means converge mathematically? -> explanation (theoretical mechanism, not user instructions).",
            "Run this script for me on your server. -> unsupported_action (unsupported external execution request).",
        ],
        annotation_guidance="Applies when the user wants instructions on how to accomplish or replicate a task, whether in code, experimental protocol, or configuration.",
    ),
    IntentCategoryEnum.ANALYTICAL_REASONING.value: IntentCategory(
        id=IntentCategoryEnum.ANALYTICAL_REASONING.value,
        name="Analytical Reasoning",
        description="The user asks for evaluation, critique, inference, deductive reasoning, causal analysis, or mathematical interpretation based on evidence.",
        inclusion_rules=[
            "Queries asking for critique, strengths/weaknesses, conclusions, implications, or causal deductions.",
            "Questions asking 'Why did the authors conclude X?' or 'What evidence supports claim Y?'.",
        ],
        exclusion_rules=[
            "Do not use if the query is a simple factual verification (use factual_lookup).",
            "Do not use if the query merely asks for verbatim quotations or page numbers (use source_evidence).",
        ],
        positive_examples=[
            "Why did the proposed model perform poorly on out-of-domain data?",
            "What conclusions can be drawn from the ablation study results?",
            "Evaluate the soundness of the statistical methodology.",
            "What relationship exists between learning rate and gradient explosion in section 4?",
            "Critique the limitations acknowledged by the researchers.",
        ],
        borderline_examples=[
            "Where does the paper mention the limitations? -> source_evidence (asking for location of text).",
            "Explain what gradient explosion means. -> definition or explanation (terminological understanding).",
        ],
        annotation_guidance="Identifies requests for critical thinking, synthesis of evidence, and deductive interpretation of document contents.",
    ),
    IntentCategoryEnum.INFORMATION_EXTRACTION.value: IntentCategory(
        id=IntentCategoryEnum.INFORMATION_EXTRACTION.value,
        name="Information Extraction",
        description="The user asks to identify, extract, and list structured entities, parameters, datasets, metrics, dates, or tabular items distributed across sources.",
        inclusion_rules=[
            "Queries requesting structured enumeration: 'List all...', 'Extract every...', 'Find all instances of...'.",
            "Compiling named entities, datasets, hyperlinks, or hyperparameter lists from documents.",
        ],
        exclusion_rules=[
            "Do not use if the user seeks a single isolated datum (use factual_lookup).",
            "Do not use if the user asks for a narrative summary of the document (use summarization).",
        ],
        positive_examples=[
            "List all machine learning algorithms mentioned in the paper.",
            "Extract all evaluation benchmarks and datasets used by the authors.",
            "Find all hyperparameter values reported for the baseline models.",
            "Extract every author affiliation listed in the document.",
            "Compile a list of all software packages and versions cited.",
        ],
        borderline_examples=[
            "What dataset was used? -> factual_lookup (single factual query).",
            "Summarize the datasets section. -> summarization (narrative summary requested).",
        ],
        annotation_guidance="Focuses on comprehensive or structured cataloging of entities, attributes, or elements from the text.",
    ),
    IntentCategoryEnum.SOURCE_EVIDENCE.value: IntentCategory(
        id=IntentCategoryEnum.SOURCE_EVIDENCE.value,
        name="Source Evidence",
        description="The user explicitly requests citations, quotations, verifiable references, page numbers, or the exact document origin of a claim.",
        inclusion_rules=[
            "Queries asking 'Where is X mentioned?', 'Give me the page number for Y', 'Quote the exact text for Z'.",
            "Explicit requests for source verification or traceability.",
        ],
        exclusion_rules=[
            "Do not use if the user asks a substantive question without specifically requesting evidence origin or citations.",
        ],
        positive_examples=[
            "Where does the paper mention the 95% accuracy claim?",
            "Give me the exact page number and paragraph supporting this statement.",
            "Show me the source excerpt where the authors discuss ethical concerns.",
            "Which document in my workspace contains this finding?",
            "Provide the direct quotation that defines the loss function.",
        ],
        borderline_examples=[
            "What is the accuracy of the model? -> factual_lookup (substantive question, does not ask for source location).",
            "Why is the accuracy 95%? -> explanation / analytical_reasoning.",
        ],
        annotation_guidance="Highest priority when source location, page numbers, or explicit quotations are demanded by the user.",
    ),
    IntentCategoryEnum.RECOMMENDATION.value: IntentCategory(
        id=IntentCategoryEnum.RECOMMENDATION.value,
        name="Recommendation",
        description="The user asks for advice, selection guidance, or an informed suggestion on which option, method, tool, or document is best suited for their purpose.",
        inclusion_rules=[
            "Queries asking 'Which should I use?', 'What is recommended for...', 'Which paper is best suited for...'.",
            "Seeking prescriptive guidance based on evidence in the uploaded documents.",
        ],
        exclusion_rules=[
            "Do not use if the user merely asks to compare two methods objectively without asking for a recommendation (use comparison).",
            "Do not use if the user asks for external recommendations unrelated to the knowledge base (use unsupported_action).",
        ],
        positive_examples=[
            "Which embedding model should I choose for dense retrieval based on these benchmarks?",
            "Which methodology is most appropriate for a low-resource setting according to the paper?",
            "Recommend the most relevant paper in my collection for learning transformer architectures.",
            "Which indexing strategy is better for my workload based on the database report?",
            "What would you suggest as the best starting chapter for a beginner?",
        ],
        borderline_examples=[
            "Compare model A and model B. -> comparison (objective comparison without recommending one).",
            "Recommend a good movie to watch tonight. -> unsupported_action (unrelated external consumer recommendation).",
        ],
        annotation_guidance="Applies when the query asks for decision support or an evidence-backed recommendation among alternatives.",
    ),
    IntentCategoryEnum.GENERAL_CONVERSATION.value: IntentCategory(
        id=IntentCategoryEnum.GENERAL_CONVERSATION.value,
        name="General Conversation",
        description="Conversational greetings, pleasantries, gratitude, acknowledgements, or meta-interaction not requiring knowledge-base document retrieval.",
        inclusion_rules=[
            "Salutations, farewells, 'Thank you', 'How are you?', 'Who are you?'.",
            "Conversational meta-dialogue that does not request substantive document intelligence.",
        ],
        exclusion_rules=[
            "Do not classify every short query as general conversation (e.g. 'What is BM25?' is definition).",
            "Do not use if the greeting is combined with a research question (the research question takes precedence).",
        ],
        positive_examples=[
            "Hello there!",
            "Good morning.",
            "Thank you so much for your help.",
            "What can you do?",
            "That's very helpful, thanks!",
        ],
        borderline_examples=[
            "Hello, can you summarize the uploaded document? -> summarization (substantive research request overrides greeting).",
            "Thanks. Now what is the difference between SVM and Random Forest? -> comparison (substantive question overrides).",
        ],
        annotation_guidance="Operational category. If a greeting or courtesy accompanies an actual knowledge query, categorize under the knowledge query intent.",
    ),
    IntentCategoryEnum.UNSUPPORTED_ACTION.value: IntentCategory(
        id=IntentCategoryEnum.UNSUPPORTED_ACTION.value,
        name="Unsupported Action",
        description="The user requests an external, transactional, physical, or operational action that falls completely outside Knovera's knowledge retrieval capabilities.",
        inclusion_rules=[
            "Requests to book flights, send emails, make payments, operate external systems, or execute arbitrary device control.",
            "Requests for actions not supported by an academic document intelligence platform.",
        ],
        exclusion_rules=[
            "Do not use simply because a factual question is not contained in the uploaded documents (that is still factual_lookup).",
            "Do not use for code implementation questions (those are procedural_guidance).",
        ],
        positive_examples=[
            "Book a flight to New York for next Friday.",
            "Send an email to my professor with my assignment attached.",
            "Reboot my computer right now.",
            "Make a credit card payment of $50.",
            "Turn off the lights in the living room.",
        ],
        borderline_examples=[
            "How do I write an email to my professor asking for an extension? -> procedural_guidance (asking for advice/instructions, not asking the system to send an email).",
            "Where can I find flight booking APIs in Python? -> factual_lookup / information_extraction.",
        ],
        annotation_guidance="Operational category. Identifies requests for external system agency or transactional execution beyond Knovera's software boundary.",
    ),
    IntentCategoryEnum.AMBIGUOUS.value: IntentCategory(
        id=IntentCategoryEnum.AMBIGUOUS.value,
        name="Ambiguous",
        description="The query is too vague, fragmented, or context-deprived to discern a clear research intent, even considering potential conversational context.",
        inclusion_rules=[
            "Completely fragmented or deictic phrases lacking referents: 'That one', 'Do it', 'What about that?'.",
            "Queries where the intended task is indeterminate.",
        ],
        exclusion_rules=[
            "Do not use as a lazy fallback when an intent can reasonably be inferred.",
            "Do not use for technical acronyms entered as standalone queries (e.g. 'BM25' is definition).",
        ],
        positive_examples=[
            "That one.",
            "Do it now.",
            "What about that?",
            "Explain the second one.",
            "More.",
        ],
        borderline_examples=[
            "BM25 -> definition (standalone concept lookup).",
            "Why? -> ambiguous (unless previous turn context provides the target assertion).",
        ],
        annotation_guidance="Operational category. Use only when the query text is genuinely insufficient to determine what operation the user wants to perform.",
    ),
}


class TaxonomyRegistry:
    """Registry maintaining authoritative query intent categories and disambiguation rules."""

    version: str = TAXONOMY_VERSION

    @classmethod
    def get_version(cls) -> str:
        """Returns current taxonomy version string."""
        return cls.version

    @classmethod
    def list_categories(cls) -> List[IntentCategory]:
        """Returns list of all registered IntentCategory objects."""
        return list(_INTENT_DEFINITIONS.values())

    @classmethod
    def list_category_ids(cls) -> List[str]:
        """Returns list of all registered intent category ID strings."""
        return list(_INTENT_DEFINITIONS.keys())

    @classmethod
    def get_category(cls, category_id: str) -> IntentCategory:
        """Retrieves IntentCategory by ID.
        
        Raises:
            KeyError: if category_id is not registered.
        """
        if category_id not in _INTENT_DEFINITIONS:
            raise KeyError(
                f"Unknown intent category '{category_id}'. Valid categories: {cls.list_category_ids()}"
            )
        return _INTENT_DEFINITIONS[category_id]

    @classmethod
    def is_valid_category(cls, category_id: str) -> bool:
        """Checks if category_id is a registered taxonomy category."""
        return category_id in _INTENT_DEFINITIONS

    @classmethod
    def get_precedence_rank(cls, category_id: str) -> int:
        """Returns integer precedence rank for multi-intent disambiguation (lower = higher priority).
        
        Returns 999 for operational categories.
        """
        if category_id in MULTI_INTENT_PRECEDENCE:
            return MULTI_INTENT_PRECEDENCE.index(category_id)
        return 999

    @classmethod
    def resolve_multi_intent(cls, candidate_intents: List[str]) -> str:
        """Resolves dominant primary intent among multiple candidate intents using precedence rules."""
        if not candidate_intents:
            return IntentCategoryEnum.AMBIGUOUS.value

        valid_intents = [c for c in candidate_intents if cls.is_valid_category(c)]
        if not valid_intents:
            return IntentCategoryEnum.AMBIGUOUS.value

        # Sort by precedence rank ascending
        sorted_intents = sorted(valid_intents, key=lambda c: cls.get_precedence_rank(c))
        return sorted_intents[0]

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Serializes taxonomy to structured dictionary matching JSON artifact format."""
        return {
            "version": cls.version,
            "category_count": len(_INTENT_DEFINITIONS),
            "categories": {cid: cat.model_dump() for cid, cat in _INTENT_DEFINITIONS.items()},
            "multi_intent_precedence": MULTI_INTENT_PRECEDENCE,
            "operational_categories": OPERATIONAL_CATEGORIES,
        }
