"""Service for C10.9: Multi-Dimensional Corpus Coverage Gap Analysis.

Analyzes an authorized corpus of 2 to 10 research papers to evaluate coverage across:
- Research Objectives and Hypotheses
- Methodological Designs and Approaches
- Datasets, Benchmarks, and Corpora
- Target Populations and Demographics
- Evaluation Dimensions and Outcome Metrics

Explicit Scope Rule:
All gaps detected are strictly labeled as 'corpus_coverage_gap' reflecting coverage
within the user's selected corpus only, never claiming universal gaps in scientific literature.
"""

from collections import Counter
import logging
from typing import Any, Dict, List, Optional, Set
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from backend.app.models.document import Document
from backend.app.models.research_intelligence import (
    DocumentCoverageAnalysisRun,
    DocumentCoverageGap,
    ResearchFinding,
    ResearchMetadataProfile,
    ResearchMethodologyProfile,
    ResearchObjectiveProfile,
)
from backend.app.schemas.research_intelligence import CoverageRunRequest

logger = logging.getLogger(__name__)


class DocumentCoverageService:
    """Computes transparent, source-grounded coverage matrices and gaps across selected papers."""

    def __init__(self, db: Session):
        self.db = db

    def analyze_coverage(
        self,
        workspace_id: uuid.UUID,
        request: CoverageRunRequest,
    ) -> DocumentCoverageAnalysisRun:
        """Execute coverage gap analysis on 2-10 documents in a workspace."""
        doc_ids = request.document_ids
        if len(doc_ids) < 2 or len(doc_ids) > 10:
            raise ValueError("Coverage analysis requires between 2 and 10 documents")

        # 1. Fetch documents
        docs = list(
            self.db.execute(
                select(Document).where(
                    Document.id.in_(doc_ids),
                    Document.workspace_id == workspace_id,
                )
            ).scalars().all()
        )
        if len(docs) != len(doc_ids):
            raise ValueError("One or more documents do not exist or belong to another workspace")

        doc_id_strs = [str(d.id) for d in docs]
        doc_titles = {
            str(d.id): (d.extraction_metadata.get("file_title") if d.extraction_metadata else None) or d.original_filename
            for d in docs
        }

        # 2. Fetch profiles
        metadatas = list(
            self.db.execute(
                select(ResearchMetadataProfile).where(
                    ResearchMetadataProfile.document_id.in_(doc_ids),
                    ResearchMetadataProfile.workspace_id == workspace_id,
                )
            ).scalars().all()
        )
        objectives = list(
            self.db.execute(
                select(ResearchObjectiveProfile).where(
                    ResearchObjectiveProfile.document_id.in_(doc_ids),
                    ResearchObjectiveProfile.workspace_id == workspace_id,
                )
            ).scalars().all()
        )
        methodologies = list(
            self.db.execute(
                select(ResearchMethodologyProfile).where(
                    ResearchMethodologyProfile.document_id.in_(doc_ids),
                    ResearchMethodologyProfile.workspace_id == workspace_id,
                )
            ).scalars().all()
        )
        findings = list(
            self.db.execute(
                select(ResearchFinding).where(
                    ResearchFinding.document_id.in_(doc_ids),
                    ResearchFinding.workspace_id == workspace_id,
                )
            ).scalars().all()
        )

        # 3. Aggregate dimensions across documents
        topics_by_doc: Dict[str, List[str]] = {}
        methods_by_doc: Dict[str, List[str]] = {}
        datasets_by_doc: Dict[str, List[str]] = {}
        populations_by_doc: Dict[str, List[str]] = {}
        metrics_by_doc: Dict[str, List[str]] = {}

        for did in doc_id_strs:
            topics_by_doc[did] = []
            methods_by_doc[did] = []
            datasets_by_doc[did] = []
            populations_by_doc[did] = []
            metrics_by_doc[did] = []

        for m in metadatas:
            did = str(m.document_id)
            fields = m.metadata_fields or {}
            kw = fields.get("keywords") or []
            if isinstance(kw, list):
                topics_by_doc[did].extend([k.strip().lower() for k in kw if isinstance(k, str)])

        for o in objectives:
            did = str(o.document_id)
            if getattr(o, "primary_objective", None):
                topics_by_doc[did].append(o.primary_objective[:80].strip().lower())
            for obj in (getattr(o, "objectives", None) or getattr(o, "primary_objectives", None) or []):
                if isinstance(obj, dict):
                    st = obj.get("normalized_text") or obj.get("original_text") or obj.get("statement", "")
                    if st:
                        topics_by_doc[did].append(st[:80].strip().lower())

        for meth in methodologies:
            did = str(meth.document_id)
            for app in (getattr(meth, "research_approaches", None) or []):
                methods_by_doc[did].append(str(app).lower())
            design = getattr(meth, "study_design", None)
            if isinstance(design, dict) and design.get("approach"):
                methods_by_doc[did].append(str(design["approach"]).lower())

            for ds in (getattr(meth, "datasets", None) or getattr(meth, "datasets_used", None) or []):
                if isinstance(ds, dict):
                    name = ds.get("name") or ds.get("dataset_name")
                    if name:
                        datasets_by_doc[did].append(str(name).lower())
                    pop = ds.get("population")
                    if pop:
                        populations_by_doc[did].append(str(pop).lower())

            for pop in (getattr(meth, "target_populations", None) or []):
                if isinstance(pop, dict) and pop.get("population_name"):
                    populations_by_doc[did].append(str(pop["population_name"]).lower())

            for metric in (getattr(meth, "evaluation_metrics", None) or getattr(meth, "metrics_and_evaluation", None) or []):
                if isinstance(metric, dict):
                    mname = metric.get("name") or metric.get("metric_name")
                    if mname:
                        metrics_by_doc[did].append(str(mname).lower())

        for f in findings:
            did = str(f.document_id)
            if f.outcome_variable:
                metrics_by_doc[did].append(f.outcome_variable.strip().lower())

        # 4. Compute distributions and build coverage matrix
        coverage_matrix = {
            "documents": [
                {"id": did, "title": doc_titles.get(did, "Untitled"), "topics": len(topics_by_doc[did]),
                 "methods": len(methods_by_doc[did]), "datasets": len(datasets_by_doc[did]),
                 "metrics": len(metrics_by_doc[did])}
                for did in doc_id_strs
            ],
            "dimension_totals": {
                "topics": sum(len(v) for v in topics_by_doc.values()),
                "methods": sum(len(v) for v in methods_by_doc.values()),
                "datasets": sum(len(v) for v in datasets_by_doc.values()),
                "populations": sum(len(v) for v in populations_by_doc.values()),
                "metrics": sum(len(v) for v in metrics_by_doc.values()),
            }
        }

        # 5. Detect Gaps
        gaps_to_create = []

        # Gap Check: Datasets
        all_datasets = [d for ds in datasets_by_doc.values() for d in ds]
        dataset_counts = Counter(all_datasets)
        docs_with_datasets = sum(1 for ds in datasets_by_doc.values() if ds)
        if docs_with_datasets == 0:
            gaps_to_create.append({
                "gap_type": "documentation_gap",
                "dimension": "dataset",
                "title": "Corpus Lacks Explicit Dataset Declarations",
                "description": "None of the selected research documents explicitly defined standard evaluation datasets in their methodology profiles.",
                "severity": "medium",
                "affected_documents": doc_id_strs,
                "candidate_research_direction": "Document or verify standardized benchmarking datasets across these studies to enable empirical replicability.",
                "suggested_inquiries": ["What public datasets were used in the evaluation?", "Can the experimental findings be reproduced on standardized corpora?"],
            })
        elif docs_with_datasets < len(doc_id_strs):
            missing_docs = [did for did, ds in datasets_by_doc.items() if not ds]
            gaps_to_create.append({
                "gap_type": "corpus_coverage_gap",
                "dimension": "dataset",
                "title": f"Partial Dataset Evaluation ({docs_with_datasets}/{len(doc_id_strs)} papers)",
                "description": f"Only {docs_with_datasets} out of {len(doc_id_strs)} selected papers report empirical datasets, creating an evidence gap for cross-paper meta-analysis.",
                "severity": "medium",
                "affected_documents": missing_docs,
                "candidate_research_direction": "Evaluate models from ungrounded papers on the common datasets used by peer papers in this corpus.",
                "suggested_inquiries": ["How do findings in non-empirical papers align with reported dataset results?"],
            })

        # Gap Check: Metrics alignment
        all_metrics = [m for ms in metrics_by_doc.values() for m in ms]
        metric_counts = Counter(all_metrics)
        shared_metrics = [m for m, c in metric_counts.items() if c >= 2]
        if not shared_metrics and len(all_metrics) > 0:
            gaps_to_create.append({
                "gap_type": "comparative_evidence_gap",
                "dimension": "metric",
                "title": "Disjoint Evaluation Metrics Across Corpus",
                "description": "Selected documents utilize disjoint outcome metrics with zero shared metrics across the papers, preventing direct quantitative meta-comparison.",
                "severity": "high",
                "affected_documents": doc_id_strs,
                "candidate_research_direction": "Establish a unified benchmarking protocol evaluating all proposed methodologies under identical metrics.",
                "suggested_inquiries": ["What standard metric can be computed across all approaches to permit direct ranking?"],
            })

        # Gap Check: Population Diversity
        docs_with_pop = sum(1 for pop in populations_by_doc.values() if pop)
        if docs_with_pop < len(doc_id_strs):
            gaps_to_create.append({
                "gap_type": "corpus_coverage_gap",
                "dimension": "population",
                "title": "Underspecified or Homogeneous Population Representation",
                "description": "Target user populations or demographic constraints are not uniformly reported across this corpus.",
                "severity": "low",
                "affected_documents": [did for did, pop in populations_by_doc.items() if not pop],
                "candidate_research_direction": "Test generalizability across diverse user populations and non-standard domain environments.",
                "suggested_inquiries": ["Do these methodologies generalize beyond the initial trial demographics?"],
            })

        # Open Candidate Research Direction
        gaps_to_create.append({
            "gap_type": "candidate_research_direction",
            "dimension": "objective",
            "title": "Cross-Method Synthesis Exploration",
            "description": f"Synthesis of objectives across {len(doc_id_strs)} papers suggests opportunities for hybrid integration combining reported methodological strengths.",
            "severity": "informational",
            "affected_documents": doc_id_strs,
            "candidate_research_direction": "Formulate a unified hybrid architecture that combines the complementary techniques reported in this corpus.",
            "suggested_inquiries": ["Can the strengths of paper A's approach overcome the stated limitations of paper B?"],
        })

        gap_summary = {
            "total_gaps_identified": len(gaps_to_create),
            "high_severity": sum(1 for g in gaps_to_create if g["severity"] == "high"),
            "medium_severity": sum(1 for g in gaps_to_create if g["severity"] == "medium"),
            "low_severity": sum(1 for g in gaps_to_create if g["severity"] == "low"),
            "informational": sum(1 for g in gaps_to_create if g["severity"] == "informational"),
            "corpus_size": len(doc_id_strs),
            "scope_notice": "Coverage findings represent gaps strictly within the selected corpus and do not imply universal gaps in the literature.",
        }

        # 6. Persist Run & Gaps
        run_record = DocumentCoverageAnalysisRun(
            workspace_id=workspace_id,
            document_ids=doc_id_strs,
            total_documents=len(doc_id_strs),
            analysis_snapshot={
                "doc_titles": doc_titles,
                "dimension_counts": dict(coverage_matrix["dimension_totals"]),
            },
            coverage_matrix=coverage_matrix,
            gap_summary=gap_summary,
            corpus_only_scope=True,
        )
        self.db.add(run_record)
        self.db.flush()

        for g in gaps_to_create:
            gap_record = DocumentCoverageGap(
                run_id=run_record.id,
                workspace_id=workspace_id,
                gap_type=g["gap_type"],
                dimension=g["dimension"],
                title=g["title"],
                description=g["description"],
                severity=g["severity"],
                affected_documents=g["affected_documents"],
                candidate_research_direction=g.get("candidate_research_direction"),
                suggested_inquiries=g.get("suggested_inquiries", []),
            )
            self.db.add(gap_record)

        self.db.commit()
        self.db.refresh(run_record)
        return run_record

    def list_runs(
        self,
        workspace_id: uuid.UUID,
        limit: int = 10,
    ) -> List[DocumentCoverageAnalysisRun]:
        """Fetch past coverage runs with gaps eager loaded."""
        stmt = (
            select(DocumentCoverageAnalysisRun)
            .where(DocumentCoverageAnalysisRun.workspace_id == workspace_id)
            .options(joinedload(DocumentCoverageAnalysisRun.gaps))
            .order_by(DocumentCoverageAnalysisRun.created_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).unique().scalars().all())

    def get_run(
        self,
        workspace_id: uuid.UUID,
        run_id: uuid.UUID,
    ) -> Optional[DocumentCoverageAnalysisRun]:
        """Get single coverage run by ID."""
        stmt = (
            select(DocumentCoverageAnalysisRun)
            .where(
                DocumentCoverageAnalysisRun.id == run_id,
                DocumentCoverageAnalysisRun.workspace_id == workspace_id,
            )
            .options(joinedload(DocumentCoverageAnalysisRun.gaps))
        )
        return self.db.execute(stmt).unique().scalar_one_or_none()
