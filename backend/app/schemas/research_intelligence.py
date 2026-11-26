"""Pydantic schemas for Knovera Phase 10: Research Intelligence.

Covers:
- C10.1: Research Document Metadata
- C10.2: Research Objectives, Questions, Hypotheses, Contributions
- C10.3: Research Methodology, Datasets, Variables, Setup, Metrics
- Orchestration Runs & Multi-Component Summaries
"""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Common Evidence & Provenance Schemas
# ---------------------------------------------------------------------------

class ResearchEvidenceReference(BaseModel):
    """Specific textual passage grounding an extracted research fact or metadata field."""

    model_config = ConfigDict(frozen=True)

    document_id: str
    chunk_id: Optional[str] = None
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    section_title: Optional[str] = None
    evidence_text: str = Field(..., description="Quoted or supporting excerpt from canonical document chunk")


class FieldProvenance(BaseModel):
    """Detailed provenance tracking for an extracted bibliographic or metadata field."""

    model_config = ConfigDict(extra="ignore")

    field: str
    value: Any
    extraction_status: Literal["extracted", "derived", "missing", "conflicting", "needs_review", "rejected"] = "extracted"
    source_type: Literal["document_content", "embedded_metadata", "structural", "inferred", "manual"] = "document_content"
    extraction_method: Literal["llm_assisted", "deterministic", "hybrid", "manual"] = "llm_assisted"
    validation_status: Literal["validated", "unvalidated", "needs_review", "rejected"] = "validated"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)


class MetadataConflict(BaseModel):
    """Represents competing values between embedded properties and displayed content."""

    model_config = ConfigDict(extra="ignore")

    field: str
    content_value: Optional[Any] = None
    embedded_value: Optional[Any] = None
    conflict_reason: str
    chosen_source: Optional[str] = None
    resolution_status: Literal["unresolved", "resolved_content", "resolved_embedded", "needs_review"] = "needs_review"


# ---------------------------------------------------------------------------
# C10.1 Metadata Extraction Schemas
# ---------------------------------------------------------------------------

ResearchDocumentType = Literal[
    "journal_article",
    "conference_paper",
    "preprint",
    "thesis",
    "dissertation",
    "technical_report",
    "research_proposal",
    "working_paper",
    "systematic_review",
    "survey_paper",
    "research_presentation",
    "unknown",
]


class AuthorInfo(BaseModel):
    """Bibliographic author record with order, affiliation, and identifiers."""

    model_config = ConfigDict(extra="ignore")

    name: str
    order: int = Field(default=1, ge=1)
    affiliation: Optional[str] = None
    department: Optional[str] = None
    institution: Optional[str] = None
    country: Optional[str] = None
    is_corresponding: bool = False
    orcid: Optional[str] = None


class ResearchMetadataProfileBase(BaseModel):
    document_type: ResearchDocumentType = "unknown"
    title: str
    subtitle: Optional[str] = None
    alternative_title: Optional[str] = None
    language: str = "en"
    abstract: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    authors: List[AuthorInfo] = Field(default_factory=list)
    publication_year: Optional[int] = None
    publication_date: Optional[str] = None
    journal_name: Optional[str] = None
    conference_name: Optional[str] = None
    publisher: Optional[str] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    page_range: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    isbn_issn: Optional[str] = None
    publication_status: Optional[str] = None
    funding_organization: Optional[str] = None
    acknowledgements: Optional[str] = None
    grant_identifiers: List[str] = Field(default_factory=list)
    research_domain: Optional[str] = None
    subdomain: Optional[str] = None


class ResearchMetadataProfileCreate(ResearchMetadataProfileBase):
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    document_version: str = "v1.0"
    metadata_fields: Dict[str, FieldProvenance] = Field(default_factory=dict)
    conflicts: List[MetadataConflict] = Field(default_factory=list)
    validation_status: str = "validated"


class ResearchMetadataProfileUpdate(BaseModel):
    document_type: Optional[ResearchDocumentType] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    abstract: Optional[str] = None
    keywords: Optional[List[str]] = None
    authors: Optional[List[AuthorInfo]] = None
    publication_year: Optional[int] = None
    journal_name: Optional[str] = None
    conference_name: Optional[str] = None
    doi: Optional[str] = None
    validation_status: Optional[str] = None


class ResearchMetadataProfileResponse(ResearchMetadataProfileBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    document_version: str
    metadata_fields: Dict[str, Any] = Field(default_factory=dict)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    validation_status: str
    is_manually_edited: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# C10.2 Research Objective Extraction Schemas
# ---------------------------------------------------------------------------

ObjectiveType = Literal[
    "primary_objective",
    "secondary_objective",
    "research_question",
    "hypothesis",
    "problem_statement",
    "motivation",
    "research_scope",
    "claimed_contribution",
]


class ResearchObjectiveItem(BaseModel):
    """Individual extracted research objective with original & normalized representations."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"obj_{uuid.uuid4().hex[:8]}")
    objective_type: Literal["primary_objective", "secondary_objective"] = "primary_objective"
    original_text: str
    normalized_text: Optional[str] = None
    is_primary: bool = False
    scope_details: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)
    extraction_status: Literal["extracted", "inferred", "partially_stated", "ambiguous", "missing", "conflicting"] = "extracted"
    validation_status: Literal["validated", "needs_review", "rejected"] = "validated"
    associated_concept_ids: List[str] = Field(default_factory=list)


class ResearchQuestionItem(BaseModel):
    """Explicit research question addressed by the study."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"rq_{uuid.uuid4().hex[:8]}")
    question_text: str
    normalized_text: Optional[str] = None
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)
    extraction_status: Literal["extracted", "inferred", "partially_stated", "ambiguous", "missing"] = "extracted"
    validation_status: Literal["validated", "needs_review", "rejected"] = "validated"


class ResearchHypothesisItem(BaseModel):
    """Formulated scientific or statistical hypothesis."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"hyp_{uuid.uuid4().hex[:8]}")
    hypothesis_text: str
    hypothesis_type: Literal["null", "alternative", "directional", "non_directional", "other"] = "alternative"
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)
    extraction_status: Literal["extracted", "inferred", "partially_stated"] = "extracted"
    validation_status: Literal["validated", "needs_review", "rejected"] = "validated"


class ClaimedContributionItem(BaseModel):
    """Contribution claimed by the paper authors."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"cnt_{uuid.uuid4().hex[:8]}")
    contribution_text: str
    contribution_type: Literal["proposed", "implemented", "claimed", "demonstrated"] = "claimed"
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)
    extraction_status: Literal["extracted", "inferred"] = "extracted"


class ResearchObjectiveProfileBase(BaseModel):
    primary_objective: Optional[str] = None
    problem_statement: Optional[str] = None
    motivation: Optional[str] = None
    research_scope: Dict[str, Any] = Field(default_factory=dict)
    objectives: List[ResearchObjectiveItem] = Field(default_factory=list)
    research_questions: List[ResearchQuestionItem] = Field(default_factory=list)
    hypotheses: List[ResearchHypothesisItem] = Field(default_factory=list)
    claimed_contributions: List[ClaimedContributionItem] = Field(default_factory=list)


class ResearchObjectiveProfileCreate(ResearchObjectiveProfileBase):
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    document_version: str = "v1.0"
    validation_status: str = "validated"


class ResearchObjectiveProfileUpdate(BaseModel):
    primary_objective: Optional[str] = None
    problem_statement: Optional[str] = None
    motivation: Optional[str] = None
    research_scope: Optional[Dict[str, Any]] = None
    validation_status: Optional[str] = None


class ResearchObjectiveProfileResponse(ResearchObjectiveProfileBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    document_version: str
    validation_status: str
    is_manually_edited: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# C10.3 Methodology Extraction Schemas
# ---------------------------------------------------------------------------

MethodExecutionStatus = Literal[
    "proposed",
    "planned",
    "implemented",
    "executed",
    "reported",
    "future_work",
    "unclear",
]


class DatasetItem(BaseModel):
    """Dataset or sample population utilized or analyzed in the research."""

    model_config = ConfigDict(extra="ignore")

    name: str
    source: Optional[str] = None
    collection_method: Optional[str] = None
    collection_period: Optional[str] = None
    sample_size: Optional[int] = None
    sample_size_approx: bool = False
    unit: str = "records"  # e.g., records, participants, patients, documents, images
    features_count: Optional[int] = None
    classes_count: Optional[int] = None
    population: Optional[str] = None
    sampling_strategy: Optional[str] = None
    inclusion_criteria: List[str] = Field(default_factory=list)
    exclusion_criteria: List[str] = Field(default_factory=list)
    split: Dict[str, str] = Field(default_factory=dict)  # e.g., {"training": "70%", "validation": "15%", "testing": "15%"}
    data_availability: Optional[str] = None
    execution_status: MethodExecutionStatus = "executed"
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)


class VariableItem(BaseModel):
    """Variable or research factor examined in the study."""

    model_config = ConfigDict(extra="ignore")

    name: str
    variable_type: Literal[
        "independent",
        "dependent",
        "control",
        "confounding",
        "outcome",
        "experimental_condition",
        "other",
    ] = "independent"
    measurement: Optional[str] = None
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)


class MethodModelItem(BaseModel):
    """Specific method, algorithm, model architecture, or statistical test."""

    model_config = ConfigDict(extra="ignore")

    name: str
    method_category: Literal[
        "machine_learning",
        "deep_learning",
        "statistical_test",
        "mathematical_model",
        "optimization",
        "preprocessing",
        "qualitative_analysis",
        "other",
    ] = "machine_learning"
    description: Optional[str] = None
    execution_status: MethodExecutionStatus = "executed"
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)


class ToolInstrumentItem(BaseModel):
    """Hardware, software, language, framework, or instrument used."""

    model_config = ConfigDict(extra="ignore")

    name: str
    tool_type: Literal["language", "library", "software", "hardware", "instrument", "other"] = "software"
    version: Optional[str] = None
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)


class ExperimentalSetupDetails(BaseModel):
    """Training, hardware, validation, and benchmarking configuration."""

    model_config = ConfigDict(extra="ignore")

    training_config: Dict[str, Any] = Field(default_factory=dict)
    validation_procedure: Optional[str] = None
    baselines: List[str] = Field(default_factory=list)
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)
    runs_count: Optional[int] = None
    cross_validation: Optional[str] = None
    random_seeds: List[int] = Field(default_factory=list)
    hardware_config: Optional[str] = None
    ablation_studies: List[str] = Field(default_factory=list)
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)


class EvaluationMetricItem(BaseModel):
    """Metric used to evaluate the experimental outcome."""

    model_config = ConfigDict(extra="ignore")

    name: str
    category: Literal["classification", "regression", "ranking", "retrieval", "generation", "statistical", "other"] = "classification"
    definition: Optional[str] = None
    purpose: Optional[str] = None
    split_or_dataset: Optional[str] = None
    reported_value: Optional[str] = None
    unit: Optional[str] = None
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)


class LimitationItem(BaseModel):
    """Author-acknowledged methodological limitation or caveat."""

    model_config = ConfigDict(extra="ignore")

    limitation_text: str
    category: Literal[
        "methodological",
        "sampling",
        "dataset",
        "measurement",
        "experimental",
        "generalizability",
        "reproducibility",
        "other",
    ] = "methodological"
    is_author_stated: bool = True
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)


class ResearchMethodologyProfileBase(BaseModel):
    research_approaches: List[str] = Field(default_factory=list)
    research_designs: List[str] = Field(default_factory=list)
    study_setting: Optional[str] = None
    datasets: List[DatasetItem] = Field(default_factory=list)
    variables: List[VariableItem] = Field(default_factory=list)
    methods_and_models: List[MethodModelItem] = Field(default_factory=list)
    tools_and_instruments: List[ToolInstrumentItem] = Field(default_factory=list)
    experimental_setup: ExperimentalSetupDetails = Field(default_factory=ExperimentalSetupDetails)
    evaluation_metrics: List[EvaluationMetricItem] = Field(default_factory=list)
    limitations: List[LimitationItem] = Field(default_factory=list)


class ResearchMethodologyProfileCreate(ResearchMethodologyProfileBase):
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    document_version: str = "v1.0"
    validation_status: str = "validated"


class ResearchMethodologyProfileUpdate(BaseModel):
    study_setting: Optional[str] = None
    validation_status: Optional[str] = None


class ResearchMethodologyProfileResponse(ResearchMethodologyProfileBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    run_id: Optional[uuid.UUID] = None
    document_version: str
    validation_status: str
    is_manually_edited: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Orchestration & Multi-Component Run Schemas
# ---------------------------------------------------------------------------

class ResearchAnalysisRunRequest(BaseModel):
    extract_metadata: bool = True
    extract_objectives: bool = True
    extract_methodology: bool = True
    force_regenerate: bool = False
    force_reanalysis: Optional[bool] = None

    def should_force(self) -> bool:
        if self.force_reanalysis is not None:
            return self.force_reanalysis
        return self.force_regenerate


class ResearchAnalysisRunResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    document_version: str
    status: str
    components_requested: List[str]
    metadata_status: str
    objectives_status: str
    methodology_status: str
    warnings: List[Dict[str, Any]]
    error_message: Optional[str] = None
    provider_used: Optional[str] = None
    model_used: Optional[str] = None
    prompt_version: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ResearchAnalysisOverviewResponse(BaseModel):
    document_id: uuid.UUID
    workspace_id: uuid.UUID
    document_version: str = "v1.0"
    active_run: Optional[ResearchAnalysisRunResponse] = None
    metadata_profile: Optional[ResearchMetadataProfileResponse] = None
    objective_profile: Optional[ResearchObjectiveProfileResponse] = None
    methodology_profile: Optional[ResearchMethodologyProfileResponse] = None

    model_config = ConfigDict(from_attributes=True)


class ResearchDocumentSummary(BaseModel):
    document_id: uuid.UUID
    workspace_id: uuid.UUID
    original_filename: str
    media_type: Optional[str] = None
    document_type: str = "unknown"
    title: str
    authors: List[str] = Field(default_factory=list)
    publication_year: Optional[int] = None
    primary_objective: Optional[str] = None
    has_metadata: bool = False
    has_objectives: bool = False
    has_methodology: bool = False
    last_analyzed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# C10.4 Multi-Paper Comparison Schemas
# ---------------------------------------------------------------------------

ComparisonDimension = Literal[
    "metadata",
    "objectives",
    "methodology",
    "datasets",
    "models",
    "evaluation",
    "limitations",
]

ComparisonStatus = Literal[
    "same",
    "similar",
    "different",
    "partially_overlapping",
    "not_comparable",
    "missing",
    "conflicting",
    "needs_review",
]


class ComparisonCell(BaseModel):
    """Value and provenance for a single paper on a specific dimension."""

    model_config = ConfigDict(extra="ignore")

    value: Optional[Any] = None
    display_text: str = ""
    status: ComparisonStatus = "similar"
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)


class DifferenceSummaryItem(BaseModel):
    """Pairwise or dimension-level explanation of observed differences."""

    dimension: str
    paper_a_title: str
    paper_b_title: str
    paper_a_value: Optional[str] = None
    paper_b_value: Optional[str] = None
    difference_description: str
    comparison_status: ComparisonStatus = "different"
    evidence_a: List[ResearchEvidenceReference] = Field(default_factory=list)
    evidence_b: List[ResearchEvidenceReference] = Field(default_factory=list)


class ResearchComparisonCreateRequest(BaseModel):
    document_ids: List[uuid.UUID] = Field(..., min_length=2, max_length=10)
    title: Optional[str] = "Research Comparison"
    description: Optional[str] = None
    dimensions: Optional[List[str]] = None


class ResearchComparisonResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    created_by_user_id: Optional[uuid.UUID] = None
    title: str
    description: Optional[str] = None
    document_ids: List[str]
    document_versions: Dict[str, str]
    dimensions: List[str]
    matrix: Dict[str, Dict[str, Any]]
    difference_summaries: List[DifferenceSummaryItem]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComparisonMatrixRow(BaseModel):
    dimension: str
    cells: Dict[str, ComparisonCell]


class ResearchComparisonMatrixResponse(BaseModel):
    comparison_id: uuid.UUID
    documents: List[Dict[str, Any]]
    dimensions: List[str]
    rows: List[ComparisonMatrixRow]

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# C10.5 Research Finding Extraction & Comparison Schemas
# ---------------------------------------------------------------------------

FindingType = Literal[
    "quantitative",
    "qualitative",
    "comparative",
    "null_result",
    "mixed",
    "descriptive",
]

FindingCategory = FindingType

FindingDirection = Literal[
    "positive",
    "negative",
    "null",
    "mixed",
    "descriptive",
    "unclear",
]

ComparabilityStatus = Literal[
    "comparable",
    "different_conditions",
    "different_outcomes",
    "incompatible_metrics",
    "incompatible_datasets",
    "insufficient_evidence",
    "not_comparable",
]

FindingRelationship = Literal[
    "supports",
    "consistent",
    "contradictory_candidate",
    "contradictory",
    "partially_consistent",
    "neutral",
    "different_conditions",
    "not_comparable",
    "insufficient_evidence",
    "needs_review",
    "pending_nli",
]


class ResearchFindingCreate(BaseModel):
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    document_version: str = "v1.0"
    run_id: Optional[uuid.UUID] = None
    finding_type: FindingType = "quantitative"
    original_statement: str
    normalized_statement: str
    outcome_variable: Optional[str] = None
    objective_relationship: Optional[str] = None
    method_relationship: Optional[str] = None
    dataset_relationship: Optional[str] = None
    population: Optional[str] = None
    experimental_condition: Optional[str] = None
    comparator: Optional[str] = None
    metric: Optional[str] = None
    reported_value: Optional[str] = None
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    direction: Optional[FindingDirection] = "positive"
    statistical_significance: Optional[str] = None
    confidence_interval: Optional[str] = None
    sample_size: Optional[int] = None
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)
    extraction_status: str = "extracted"
    validation_status: str = "validated"


class ResearchFindingResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    document_version: str
    run_id: Optional[uuid.UUID] = None
    finding_type: str
    original_statement: str
    normalized_statement: str
    outcome_variable: Optional[str] = None
    objective_relationship: Optional[str] = None
    method_relationship: Optional[str] = None
    dataset_relationship: Optional[str] = None
    population: Optional[str] = None
    experimental_condition: Optional[str] = None
    comparator: Optional[str] = None
    metric: Optional[str] = None
    reported_value: Optional[str] = None
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    direction: Optional[str] = "positive"
    statistical_significance: Optional[str] = None
    confidence_interval: Optional[str] = None
    sample_size: Optional[int] = None
    evidence: List[ResearchEvidenceReference] = Field(default_factory=list)
    extraction_status: str
    validation_status: str
    is_manually_edited: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResearchFindingComparisonResponse(BaseModel):
    id: uuid.UUID
    comparison_id: uuid.UUID
    finding_a_id: uuid.UUID
    finding_b_id: uuid.UUID
    paper_a_title: Optional[str] = None
    paper_b_title: Optional[str] = None
    finding_a_statement: Optional[str] = None
    finding_b_statement: Optional[str] = None
    outcome_variable: Optional[str] = None
    comparability_status: str
    preliminary_relationship: str
    nli_relation: Optional[str] = None
    final_relation: str
    comparison_rationale: Optional[str] = None
    contextual_differences: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_a: List[ResearchEvidenceReference] = Field(default_factory=list)
    evidence_b: List[ResearchEvidenceReference] = Field(default_factory=list)
    validation_status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# C10.6 NLI Model Integration Schemas
# ---------------------------------------------------------------------------

NLILabel = Literal["entailment", "contradiction", "neutral"]


class NLIInferenceRequest(BaseModel):
    premise: str = Field(..., min_length=3, max_length=2000)
    hypothesis: str = Field(..., min_length=3, max_length=2000)
    premise_doc_id: Optional[uuid.UUID] = None
    hypothesis_doc_id: Optional[uuid.UUID] = None
    bidirectional: bool = True


class NLIInferenceResponse(BaseModel):
    premise: str
    hypothesis: str
    forward_label: NLILabel
    forward_scores: Dict[str, float]
    backward_label: Optional[NLILabel] = None
    backward_scores: Optional[Dict[str, float]] = None
    aggregated_label: str
    margin: float
    abstained: bool
    confidence_level: str
    model_id: str
    model_revision: str
    pair_fingerprint: str


class CompareFindingsNLIRequest(BaseModel):
    finding_a_id: uuid.UUID
    finding_b_id: uuid.UUID


class NLIEvaluationRunRequest(BaseModel):
    dataset_name: str = "default_benchmark"
    dataset_path: Optional[str] = None
    custom_pairs: Optional[List[Dict[str, Any]]] = None


class NLIEvaluationRunResponse(BaseModel):
    id: uuid.UUID
    workspace_id: Optional[uuid.UUID] = None
    model_id: str
    model_revision: str
    dataset_name: str
    sample_count: int
    accuracy: float
    macro_f1: float
    per_class_f1: Dict[str, float]
    precision_recall_by_class: Dict[str, Any]
    confusion_matrix: Dict[str, Any]
    abstention_rate: float
    is_readiness_passed: bool
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# C10.7 Evidence Validation Schemas
# ---------------------------------------------------------------------------

ValidationStatus = Literal[
    "unvalidated",
    "structurally_valid",
    "evidence_matched",
    "supported",
    "partially_supported",
    "unsupported",
    "conflicting_evidence",
    "stale",
    "needs_review",
    "rejected",
]

ValidationTier = Literal[
    "tier_1_exact_span",
    "tier_2_normalized_overlap",
    "tier_3_semantic_nli",
    "tier_4_heuristic",
]


class EvidenceValidationRequest(BaseModel):
    document_id: uuid.UUID
    claim_type: str = "finding"
    claim_id: Optional[uuid.UUID] = None
    claim_text: str = Field(..., min_length=3)
    chunk_id: Optional[uuid.UUID] = None
    target_page_number: Optional[int] = None
    target_section: Optional[str] = None
    revalidate_stale: bool = False


class ValidateFindingRequest(BaseModel):
    finding_id: uuid.UUID


class EvidenceValidationResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_id: uuid.UUID
    claim_type: str
    claim_id: Optional[uuid.UUID] = None
    claim_text: str
    target_chunk_id: Optional[uuid.UUID] = None
    target_page_number: Optional[int] = None
    target_section: Optional[str] = None
    validation_status: str
    validation_tier: str
    confidence_score: float
    exact_match: bool
    normalized_overlap: float
    numeric_match: Optional[bool] = None
    qualifier_match: Optional[bool] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    supporting_text_excerpt: Optional[str] = None
    rejection_reason: Optional[str] = None
    validation_metadata: Dict[str, Any] = Field(default_factory=dict)
    is_stale: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# C10.8 Contradiction Detection Schemas
# ---------------------------------------------------------------------------

ContradictionCategory = Literal[
    "direct_contradiction_candidate",
    "contextual_difference",
    "metric_difference",
    "population_difference",
    "dataset_difference",
    "partial_agreement",
    "consistent",
    "neutral_or_unrelated",
    "insufficient_evidence",
]

ContradictionReviewStatus = Literal[
    "candidate",
    "automatically_assessed",
    "needs_review",
    "human_reviewed",
    "confirmed",
    "rejected",
    "superseded",
]


class ContradictionDetectRequest(BaseModel):
    comparison_id: Optional[uuid.UUID] = None
    finding_a_id: uuid.UUID
    finding_b_id: uuid.UUID
    force_reevaluation: bool = False


class ContradictionReviewRequest(BaseModel):
    action: Literal["confirm", "reject", "flag_contextual", "reopen"]
    notes: Optional[str] = None


class ContradictionReviewResponse(BaseModel):
    id: uuid.UUID
    contradiction_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    previous_status: str
    new_status: str
    review_action: str
    review_notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResearchContradictionResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    comparison_id: Optional[uuid.UUID] = None
    finding_a_id: uuid.UUID
    finding_b_id: uuid.UUID
    document_a_id: uuid.UUID
    document_b_id: uuid.UUID
    finding_a_statement: Optional[str] = None
    finding_b_statement: Optional[str] = None
    paper_a_title: Optional[str] = None
    paper_b_title: Optional[str] = None
    contradiction_category: str
    evidence_validity_a: str
    evidence_validity_b: str
    comparability_status: str
    contextual_differences: List[str] = Field(default_factory=list)
    stage_breakdown: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float
    nli_relation: Optional[str] = None
    review_status: str
    human_verified: bool
    reviewer_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    reviews: List[ContradictionReviewResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# C10.9 Document Coverage Gap Analysis Schemas
# ---------------------------------------------------------------------------

class CoverageRunRequest(BaseModel):
    document_ids: List[uuid.UUID] = Field(..., min_length=2, max_length=10)
    custom_dimensions: Optional[List[str]] = None


class CoverageGapItem(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    workspace_id: uuid.UUID
    gap_type: str
    dimension: str
    title: str
    description: str
    severity: str
    affected_documents: List[str] = Field(default_factory=list)
    candidate_research_direction: Optional[str] = None
    suggested_inquiries: List[str] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentCoverageRunResponse(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    document_ids: List[str]
    total_documents: int
    analysis_snapshot: Dict[str, Any] = Field(default_factory=dict)
    coverage_matrix: Dict[str, Any] = Field(default_factory=dict)
    gap_summary: Dict[str, Any] = Field(default_factory=dict)
    corpus_only_scope: bool = True
    created_at: datetime
    gaps: List[CoverageGapItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# C10.10 Research Intelligence Dashboard Schemas
# ---------------------------------------------------------------------------

class ResearchDashboardSummaryResponse(BaseModel):
    workspace_id: uuid.UUID
    total_research_documents: int
    extraction_stats: Dict[str, int]
    total_comparisons: int
    total_findings: int
    validation_stats: Dict[str, int]
    contradiction_stats: Dict[str, int]
    coverage_stats: Dict[str, Any]
    recent_contradictions: List[ResearchContradictionResponse] = Field(default_factory=list)
    recent_validations: List[EvidenceValidationResponse] = Field(default_factory=list)
    recent_gaps: List[CoverageGapItem] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
