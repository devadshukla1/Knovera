"""ORM Models for Knovera Phase 10: Research Intelligence.

Covers:
- C10.1: Research Document Metadata Profiles
- C10.2: Research Objective Profiles
- C10.3: Research Methodology Profiles
- Cross-Chunk Orchestration Runs
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from backend.app.db.base import Base

if TYPE_CHECKING:
    from backend.app.models.document import Document
    from backend.app.models.workspace import Workspace
    from backend.app.models.user import User


class ResearchAnalysisRun(Base):
    """Execution audit and lifecycle tracking for research-document analysis runs."""

    __tablename__ = "research_analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_version: Mapped[str] = mapped_column(
        String(50),
        default="v1.0",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(40),
        default="queued",
        nullable=False,
        index=True,
    )  # queued, running, completed, completed_with_warnings, partially_completed, failed
    components_requested: Mapped[List[str]] = mapped_column(
        JSON,
        default=lambda: ["metadata", "objectives", "methodology"],
        nullable=False,
    )
    metadata_status: Mapped[str] = mapped_column(
        String(30),
        default="not_requested",
        nullable=False,
    )  # not_requested, queued, running, completed, needs_review, failed
    objectives_status: Mapped[str] = mapped_column(
        String(30),
        default="not_requested",
        nullable=False,
    )  # not_requested, queued, running, completed, needs_review, failed
    methodology_status: Mapped[str] = mapped_column(
        String(30),
        default="not_requested",
        nullable=False,
    )  # not_requested, queued, running, completed, needs_review, failed
    warnings: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    provider_used: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
    )
    model_used: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    prompt_version: Mapped[str] = mapped_column(
        String(50),
        default="v1.0",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")


    document: Mapped["Document"] = relationship("Document")

    __table_args__ = (
        Index("ix_res_runs_ws_doc", "workspace_id", "document_id"),
        Index("ix_res_runs_ws_status", "workspace_id", "status"),
    )


class ResearchMetadataProfile(Base):
    """Bibliographic, identity, and descriptive metadata profile for a research document (C10.1)."""

    __tablename__ = "research_metadata_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("research_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_version: Mapped[str] = mapped_column(
        String(50),
        default="v1.0",
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(
        String(60),
        default="unknown",
        nullable=False,
    )  # journal_article, conference_paper, preprint, thesis, dissertation, technical_report, etc.
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    subtitle: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    alternative_title: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    language: Mapped[str] = mapped_column(
        String(20),
        default="en",
        nullable=False,
    )
    abstract: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    keywords: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    authors: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{name, order, affiliation, department, institution, country, is_corresponding, orcid}]
    publication_year: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )
    publication_date: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    journal_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    conference_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    publisher: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    volume: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    issue: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    page_range: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    doi: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
        index=True,
    )
    arxiv_id: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
    )
    isbn_issn: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
    )
    publication_status: Mapped[Optional[str]] = mapped_column(
        String(60),
        nullable=True,
    )  # published, preprint, accepted, under_review, working_paper
    funding_organization: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    acknowledgements: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    grant_identifiers: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    research_domain: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    subdomain: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    metadata_fields: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )  # field -> {value, extraction_status, evidence, source_type, extraction_method, validation_status, confidence}
    conflicts: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # competing candidates when embedded metadata conflicts with content
    validation_status: Mapped[str] = mapped_column(
        String(30),
        default="validated",
        nullable=False,
    )  # validated, unvalidated, needs_review, rejected
    is_manually_edited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")


    document: Mapped["Document"] = relationship("Document")

    __table_args__ = (
        Index("ix_res_meta_ws_doc", "workspace_id", "document_id"),
        Index("ix_res_meta_doc_type", "document_type"),
    )


class ResearchObjectiveProfile(Base):
    """Research objective, research question, hypothesis, and contribution profile (C10.2)."""

    __tablename__ = "research_objective_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("research_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_version: Mapped[str] = mapped_column(
        String(50),
        default="v1.0",
        nullable=False,
    )
    primary_objective: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    problem_statement: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    motivation: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    research_scope: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )  # {domain, target_population, study_environment, time_period, geographic_scope, boundaries, exclusions}
    objectives: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{id, objective_type, original_text, normalized_text, is_primary, evidence, extraction_status, validation_status, associated_concept_ids}]
    research_questions: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{id, question_text, normalized_text, evidence, extraction_status, validation_status}]
    hypotheses: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{id, hypothesis_text, hypothesis_type, evidence, extraction_status, validation_status}]
    claimed_contributions: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{id, contribution_text, contribution_type, evidence, extraction_status}]
    validation_status: Mapped[str] = mapped_column(
        String(30),
        default="validated",
        nullable=False,
    )
    is_manually_edited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")


    document: Mapped["Document"] = relationship("Document")

    __table_args__ = (
        Index("ix_res_obj_ws_doc", "workspace_id", "document_id"),
    )


class ResearchMethodologyProfile(Base):
    """Methodology, experimental setup, datasets, variables, and evaluation metrics profile (C10.3)."""

    __tablename__ = "research_methodology_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("research_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_version: Mapped[str] = mapped_column(
        String(50),
        default="v1.0",
        nullable=False,
    )
    research_approaches: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # quantitative, qualitative, mixed_methods, computational, theoretical, experimental, etc.
    research_designs: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # experiment, controlled_experiment, case_study, benchmark_evaluation, etc.
    study_setting: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    datasets: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{name, source, collection_method, collection_period, sample_size, sample_size_approx, unit, features_count, classes_count, population, sampling_strategy, inclusion_criteria, exclusion_criteria, split, data_availability, evidence, execution_status}]
    variables: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{name, variable_type, measurement, evidence}]
    methods_and_models: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{name, method_category, description, execution_status, evidence}]
    tools_and_instruments: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{name, tool_type, version, evidence}]
    experimental_setup: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )  # {training_config, validation_procedure, baselines, hyperparameters, runs_count, cross_validation, seeds, hardware_config, ablation_studies, evidence}
    evaluation_metrics: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{name, category, definition, purpose, split_or_dataset, reported_value, unit, evidence}]
    limitations: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )  # [{limitation_text, category, is_author_stated, evidence}]
    validation_status: Mapped[str] = mapped_column(
        String(30),
        default="validated",
        nullable=False,
    )
    is_manually_edited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")


    document: Mapped["Document"] = relationship("Document")

    __table_args__ = (
        Index("ix_res_meth_ws_doc", "workspace_id", "document_id"),
    )


# ===========================================================================
# C10.4 Multi-Paper Comparison Models
# ===========================================================================

class ResearchComparisonProfile(Base):
    """Multi-document structured comparison profile and matrix (C10.4)."""

    __tablename__ = "research_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default="Research Comparison",
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    document_ids: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    document_versions: Mapped[Dict[str, str]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    dimensions: Mapped[List[str]] = mapped_column(
        JSON,
        default=lambda: [
            "metadata",
            "objectives",
            "methodology",
            "datasets",
            "models",
            "evaluation",
            "limitations",
        ],
        nullable=False,
    )
    matrix: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    difference_summaries: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="completed",
        nullable=False,
        index=True,
    )  # completed, needs_review, partial, failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("ix_research_comparisons_ws_status", "workspace_id", "status"),
    )


# ===========================================================================
# C10.5 Research Finding Extraction & Comparison Models
# ===========================================================================

class ResearchFinding(Base):
    """Discrete, source-grounded empirical finding extracted from a paper (C10.5)."""

    __tablename__ = "research_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_version: Mapped[str] = mapped_column(
        String(50),
        default="v1.0",
        nullable=False,
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("research_analysis_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    finding_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # quantitative, qualitative, comparative, null_result, mixed, descriptive
    original_statement: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    normalized_statement: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    outcome_variable: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    objective_relationship: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    method_relationship: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    dataset_relationship: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    population: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    experimental_condition: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    comparator: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    metric: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )
    reported_value: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    numeric_value: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )
    unit: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    direction: Mapped[Optional[str]] = mapped_column(
        String(30),
        default="positive",
        nullable=True,
    )  # positive, negative, null, mixed, descriptive, unclear
    statistical_significance: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    confidence_interval: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    sample_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    evidence: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    extraction_status: Mapped[str] = mapped_column(
        String(30),
        default="extracted",
        nullable=False,
    )
    validation_status: Mapped[str] = mapped_column(
        String(30),
        default="validated",
        nullable=False,
    )
    is_manually_edited: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    workspace: Mapped["Workspace"] = relationship("Workspace")


    document: Mapped["Document"] = relationship("Document")

    __table_args__ = (
        Index("ix_res_finding_ws_doc", "workspace_id", "document_id"),
        Index("ix_res_finding_metric", "workspace_id", "metric"),
    )


class ResearchFindingComparison(Base):
    """Pairwise alignment, comparability check, and relation synthesis between two findings (C10.5)."""

    __tablename__ = "research_finding_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    comparison_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("research_comparisons.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_a_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("research_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_b_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("research_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outcome_variable: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    comparability_status: Mapped[str] = mapped_column(
        String(50),
        default="comparable",
        nullable=False,
    )  # comparable, different_conditions, different_outcomes, incompatible_metrics, incompatible_datasets, not_comparable
    preliminary_relationship: Mapped[str] = mapped_column(
        String(50),
        default="pending_nli",
        nullable=False,
    )  # consistent, contradictory_candidate, partially_consistent, different_outcomes, different_conditions, not_comparable, insufficient_evidence, pending_nli
    comparison_rationale: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    contextual_differences: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    nli_relation: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )  # supports, consistent, contradictory, contradiction_candidate, neutral, different_conditions, not_comparable
    nli_inference_record_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("nli_inference_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    final_relation: Mapped[str] = mapped_column(
        String(50),
        default="pending_nli",
        nullable=False,
    )
    validation_status: Mapped[str] = mapped_column(
        String(30),
        default="validated",
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    finding_a: Mapped["ResearchFinding"] = relationship("ResearchFinding", foreign_keys=[finding_a_id])
    finding_b: Mapped["ResearchFinding"] = relationship("ResearchFinding", foreign_keys=[finding_b_id])


# ===========================================================================
# C10.6 Natural Language Inference (NLI) Models
# ===========================================================================

class NLIInferenceRecord(Base):
    """Inference record and cached semantic entailment/contradiction assessment (C10.6)."""

    __tablename__ = "nli_inference_records"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    model_revision: Mapped[str] = mapped_column(
        String(64),
        default="main",
        nullable=False,
    )
    pair_fingerprint: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    premise_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    hypothesis_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    premise_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    hypothesis_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    premise_source_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
    )
    hypothesis_source_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
    )
    forward_label: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )  # entailment, contradiction, neutral
    forward_scores: Mapped[Dict[str, float]] = mapped_column(
        JSON,
        nullable=False,
    )  # {"entailment": float, "contradiction": float, "neutral": float}
    backward_label: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )
    backward_scores: Mapped[Optional[Dict[str, float]]] = mapped_column(
        JSON,
        nullable=True,
    )
    aggregated_label: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )
    margin: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    abstained: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    confidence_level: Mapped[str] = mapped_column(
        String(30),
        default="moderate",
        nullable=False,
    )  # high, moderate, low, abstained
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

class NLIEvaluationRun(Base):
    """Benchmark evaluation run record assessing NLI models on research claim datasets (C10.6)."""

    __tablename__ = "nli_evaluation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    model_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    model_revision: Mapped[str] = mapped_column(
        String(64),
        default="main",
        nullable=False,
    )
    dataset_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    sample_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    accuracy: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    macro_f1: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    per_class_f1: Mapped[Dict[str, float]] = mapped_column(
        JSON,
        nullable=False,
    )
    precision_recall_by_class: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    confusion_matrix: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    abstention_rate: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    is_readiness_passed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class ResearchEvidenceValidationRecord(Base):
    """Rigorous evidence validation record connecting claims to document source chunks (C10.7)."""

    __tablename__ = "research_evidence_validations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_type: Mapped[str] = mapped_column(
        String(50),
        default="finding",
        nullable=False,
        index=True,
    )  # finding, objective, methodology, comparison_statement, custom_claim
    claim_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        index=True,
    )
    claim_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    target_chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        nullable=True,
        index=True,
    )
    target_page_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    target_section: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    validation_status: Mapped[str] = mapped_column(
        String(50),
        default="unvalidated",
        nullable=False,
        index=True,
    )  # unvalidated, structurally_valid, evidence_matched, supported, partially_supported, unsupported, conflicting_evidence, stale, needs_review, rejected
    validation_tier: Mapped[str] = mapped_column(
        String(40),
        default="tier_1_exact_span",
        nullable=False,
    )  # tier_1_exact_span, tier_2_normalized_overlap, tier_3_semantic_nli, tier_4_heuristic
    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    exact_match: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    normalized_overlap: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    numeric_match: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    qualifier_match: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )
    char_start: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    char_end: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    supporting_text_excerpt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    validation_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    is_stale: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class ResearchContradictionRecord(Base):
    """Cross-paper empirical contradiction and conflict detection record (C10.8)."""

    __tablename__ = "research_contradictions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    comparison_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("research_comparisons.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    finding_a_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("research_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finding_b_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("research_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_a_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_b_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contradiction_category: Mapped[str] = mapped_column(
        String(50),
        default="direct_contradiction_candidate",
        nullable=False,
        index=True,
    )  # direct_contradiction_candidate, contextual_difference, metric_difference, population_difference, dataset_difference, partial_agreement, consistent, neutral_or_unrelated, insufficient_evidence
    evidence_validity_a: Mapped[str] = mapped_column(
        String(40),
        default="unvalidated",
        nullable=False,
    )
    evidence_validity_b: Mapped[str] = mapped_column(
        String(40),
        default="unvalidated",
        nullable=False,
    )
    comparability_status: Mapped[str] = mapped_column(
        String(40),
        default="comparable",
        nullable=False,
    )  # comparable, conditionally_comparable, not_comparable
    contextual_differences: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    stage_breakdown: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
    )
    nli_relation: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )
    review_status: Mapped[str] = mapped_column(
        String(40),
        default="candidate",
        nullable=False,
        index=True,
    )  # candidate, automatically_assessed, needs_review, human_reviewed, confirmed, rejected, superseded
    human_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )
    reviewer_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    reviews: Mapped[List["ResearchContradictionReview"]] = relationship(
        "ResearchContradictionReview",
        back_populates="contradiction",
        cascade="all, delete-orphan",
    )


class ResearchContradictionReview(Base):
    """Audit log of human review interactions on contradiction candidate items (C10.8)."""

    __tablename__ = "research_contradiction_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    contradiction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("research_contradictions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    previous_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    new_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )
    review_action: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )  # confirm, reject, flag_contextual, reopen
    review_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    contradiction: Mapped["ResearchContradictionRecord"] = relationship(
        "ResearchContradictionRecord",
        back_populates="reviews",
    )


class DocumentCoverageAnalysisRun(Base):
    """Snapshot analysis run assessing research topic, method, and empirical coverage (C10.9)."""

    __tablename__ = "document_coverage_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_ids: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
    )
    total_documents: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    analysis_snapshot: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    coverage_matrix: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    gap_summary: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    corpus_only_scope: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    gaps: Mapped[List["DocumentCoverageGap"]] = relationship(
        "DocumentCoverageGap",
        back_populates="run",
        cascade="all, delete-orphan",
    )


class DocumentCoverageGap(Base):
    """Specific coverage gap or open research direction identified within a corpus (C10.9)."""

    __tablename__ = "document_coverage_gaps"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("document_coverage_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    gap_type: Mapped[str] = mapped_column(
        String(50),
        default="corpus_coverage_gap",
        nullable=False,
        index=True,
    )  # corpus_coverage_gap, documentation_gap, comparative_evidence_gap, candidate_research_direction
    dimension: Mapped[str] = mapped_column(
        String(50),
        default="topic",
        nullable=False,
        index=True,
    )  # topic, methodology, dataset, population, metric, objective
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        nullable=False,
    )  # high, medium, low, informational
    affected_documents: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    candidate_research_direction: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    suggested_inquiries: Mapped[List[str]] = mapped_column(
        JSON,
        default=list,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    run: Mapped["DocumentCoverageAnalysisRun"] = relationship(
        "DocumentCoverageAnalysisRun",
        back_populates="gaps",
    )
