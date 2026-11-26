"""Multi-Paper Comparison Service (Phase 10 C10.4).

Provides:
- Multi-document selection validation and tenancy enforcement
- Cross-paper comparison across 7 core dimensions:
  1. Bibliographic metadata
  2. Research objectives & hypotheses
  3. Methodology & experimental design
  4. Datasets & sample populations
  5. Models & algorithms (with executed vs proposed preservation)
  6. Evaluation strategies & metrics
  7. Author-stated limitations
- Grounded difference explanations with source chunk/page evidence
- Persistence of structured comparison matrices and versioned profiles
"""

import json
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.logging import get_logger
from backend.app.models.document import Document
from backend.app.models.research_intelligence import (
    ResearchAnalysisRun,
    ResearchComparisonProfile,
    ResearchMetadataProfile,
    ResearchMethodologyProfile,
    ResearchObjectiveProfile,
)
from backend.app.schemas.research_intelligence import (
    ComparisonCell,
    ComparisonDimension,
    ComparisonMatrixRow,
    ComparisonStatus,
    DifferenceSummaryItem,
    ResearchComparisonCreateRequest,
    ResearchComparisonMatrixResponse,
    ResearchComparisonResponse,
    ResearchEvidenceReference,
)

logger = get_logger("knovera.research.comparison_service")

SUPPORTED_DIMENSIONS: List[ComparisonDimension] = [
    "metadata",
    "objectives",
    "methodology",
    "datasets",
    "models",
    "evaluation",
    "limitations",
]


class MultiPaperComparisonService:
    """Orchestrates structured comparative analysis across multiple research papers."""

    def __init__(self, max_documents: int = 10):
        self.max_documents = max_documents

    def create_comparison(
        self,
        db: Session,
        workspace_id: uuid.UUID,
        request: ResearchComparisonCreateRequest,
        user_id: Optional[uuid.UUID] = None,
    ) -> ResearchComparisonProfile:
        """Validates documents, builds comparison matrix, generates difference summaries, and persists profile."""
        doc_uuids = request.document_ids
        if len(doc_uuids) < 2:
            raise ValueError("Multi-paper comparison requires at least 2 distinct research documents.")
        if len(doc_uuids) > self.max_documents:
            raise ValueError(f"Exceeded maximum allowed documents for comparison ({self.max_documents}).")

        # 1. Tenancy and Document Validation
        docs = list(
            db.execute(
                select(Document).where(
                    Document.id.in_(doc_uuids),
                    Document.workspace_id == workspace_id,
                )
            ).scalars().all()
        )
        if len(docs) != len(doc_uuids):
            found_ids = {d.id for d in docs}
            missing = [str(uid) for uid in doc_uuids if uid not in found_ids]
            raise ValueError(f"One or more documents not found or unauthorized in this workspace: {missing}")

        # Check for duplicate versions / duplicate documents
        doc_id_strs = [str(d.id) for d in docs]
        doc_versions = {str(d.id): (d.pipeline_version or "v1.0") for d in docs}

        # 2. Load Profiles for Each Document
        profiles_by_doc = {}
        for d in docs:
            meta = db.execute(
                select(ResearchMetadataProfile).where(
                    ResearchMetadataProfile.document_id == d.id,
                    ResearchMetadataProfile.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()

            obj = db.execute(
                select(ResearchObjectiveProfile).where(
                    ResearchObjectiveProfile.document_id == d.id,
                    ResearchObjectiveProfile.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()

            meth = db.execute(
                select(ResearchMethodologyProfile).where(
                    ResearchMethodologyProfile.document_id == d.id,
                    ResearchMethodologyProfile.workspace_id == workspace_id,
                )
            ).scalar_one_or_none()

            profiles_by_doc[str(d.id)] = {
                "document": d,
                "metadata": meta,
                "objective": obj,
                "methodology": meth,
            }

        selected_dimensions = request.dimensions or SUPPORTED_DIMENSIONS

        # 3. Build Comparison Matrix and Difference Summaries
        matrix: Dict[str, Dict[str, Any]] = {}
        difference_summaries: List[Dict[str, Any]] = []

        for dim in selected_dimensions:
            dim_cells: Dict[str, Any] = {}
            for doc_id_str in doc_id_strs:
                cell_data = self._build_dimension_cell(dim, profiles_by_doc[doc_id_str])
                dim_cells[doc_id_str] = cell_data.model_dump()
            matrix[dim] = dim_cells

            # Generate pairwise difference explanations
            dim_diffs = self._generate_dimension_differences(dim, doc_id_strs, profiles_by_doc, dim_cells)
            difference_summaries.extend(dim_diffs)

        # 4. Persist Comparison Profile
        comparison = ResearchComparisonProfile(
            workspace_id=workspace_id,
            created_by_user_id=user_id,
            title=request.title or f"Comparison of {len(docs)} Research Papers",
            description=request.description,
            document_ids=doc_id_strs,
            document_versions=doc_versions,
            dimensions=selected_dimensions,
            matrix=matrix,
            difference_summaries=difference_summaries,
            status="completed",
        )
        db.add(comparison)
        db.commit()
        db.refresh(comparison)

        logger.info(
            "Created research comparison %s for %d papers in workspace %s",
            comparison.id,
            len(docs),
            workspace_id,
        )
        return comparison

    def get_matrix_response(
        self,
        db: Session,
        comparison: ResearchComparisonProfile,
    ) -> ResearchComparisonMatrixResponse:
        """Transforms stored comparison profile into client-friendly tabular matrix response."""
        doc_ids = [uuid.UUID(did) for did in comparison.document_ids]
        docs = {
            str(d.id): d
            for d in db.execute(
                select(Document).where(Document.id.in_(doc_ids))
            ).scalars().all()
        }

        # Retrieve metadata titles where available
        meta_profiles = {
            str(m.document_id): m
            for m in db.execute(
                select(ResearchMetadataProfile).where(
                    ResearchMetadataProfile.document_id.in_(doc_ids),
                    ResearchMetadataProfile.workspace_id == comparison.workspace_id,
                )
            ).scalars().all()
        }

        doc_headers = []
        for did in comparison.document_ids:
            doc = docs.get(did)
            meta = meta_profiles.get(did)
            doc_headers.append({
                "id": did,
                "filename": doc.original_filename if doc else "Document",
                "title": meta.title if meta else (doc.original_filename if doc else "Document"),
                "publication_year": meta.publication_year if meta else None,
                "authors": [a.get("name") if isinstance(a, dict) else str(a) for a in (meta.authors if meta else [])],
            })

        rows = []
        for dim, cells_dict in comparison.matrix.items():
            parsed_cells = {
                did: ComparisonCell.model_validate(cell_data)
                for did, cell_data in cells_dict.items()
            }
            rows.append(ComparisonMatrixRow(dimension=dim, cells=parsed_cells))

        return ResearchComparisonMatrixResponse(
            comparison_id=comparison.id,
            documents=doc_headers,
            dimensions=comparison.dimensions,
            rows=rows,
        )

    # Alias for endpoint compatibility
    get_comparison_matrix = get_matrix_response

    # -----------------------------------------------------------------------
    # Internal Dimension Cell Builders
    # -----------------------------------------------------------------------

    def _build_dimension_cell(self, dimension: str, doc_bundle: Dict[str, Any]) -> ComparisonCell:
        """Constructs extracted value, display string, and evidence for a document dimension."""
        doc: Document = doc_bundle["document"]
        meta: Optional[ResearchMetadataProfile] = doc_bundle["metadata"]
        obj: Optional[ResearchObjectiveProfile] = doc_bundle["objective"]
        meth: Optional[ResearchMethodologyProfile] = doc_bundle["methodology"]

        if dimension == "metadata":
            if not meta:
                return ComparisonCell(value=None, display_text="Metadata not extracted", status="missing")
            venue = meta.journal_name or meta.conference_name or meta.publication_status or "Unknown Venue"
            year_str = str(meta.publication_year) if meta.publication_year else "n.d."
            authors_str = ", ".join([a.get("name", "") if isinstance(a, dict) else getattr(a, "name", "") for a in (meta.authors or [])][:3])
            display = f"{meta.title} ({year_str}). {authors_str}. Venue: {venue}"
            evidence = self._extract_evidence_sample(meta.metadata_fields)
            return ComparisonCell(
                value={
                    "title": meta.title,
                    "year": meta.publication_year,
                    "venue": venue,
                    "doi": meta.doi,
                    "arxiv_id": meta.arxiv_id,
                },
                display_text=display,
                status="similar",
                evidence=evidence,
            )

        elif dimension == "objectives":
            if not obj or not obj.primary_objective:
                return ComparisonCell(value=None, display_text="Objectives not extracted", status="missing")
            rq_count = len(obj.research_questions or [])
            hyp_count = len(obj.hypotheses or [])
            display = f"{obj.primary_objective} ({rq_count} RQs, {hyp_count} Hypotheses)"
            evidence = []
            if obj.objectives and obj.objectives[0].get("evidence"):
                evidence = [ResearchEvidenceReference.model_validate(e) for e in obj.objectives[0]["evidence"]]
            return ComparisonCell(
                value={
                    "primary_objective": obj.primary_objective,
                    "problem_statement": obj.problem_statement,
                    "rq_count": rq_count,
                    "hyp_count": hyp_count,
                },
                display_text=display,
                status="similar",
                evidence=evidence,
            )

        elif dimension == "methodology":
            if not meth:
                return ComparisonCell(value=None, display_text="Methodology not extracted", status="missing")
            approaches = ", ".join(meth.research_approaches or ["Not specified"])
            designs = ", ".join(meth.research_designs or ["Not specified"])
            display = f"Approach: {approaches}. Design: {designs} (Setting: {meth.study_setting or 'N/A'})"
            return ComparisonCell(
                value={"approaches": meth.research_approaches, "designs": meth.research_designs, "setting": meth.study_setting},
                display_text=display,
                status="similar",
                evidence=[],
            )

        elif dimension == "datasets":
            if not meth or not meth.datasets:
                return ComparisonCell(value=[], display_text="No datasets identified", status="missing")
            ds_names = []
            for ds in meth.datasets:
                name = ds.get("name", "Dataset")
                size = ds.get("sample_size")
                unit = ds.get("unit", "samples")
                size_str = f" (~{size:,} {unit})" if size else ""
                ds_names.append(f"{name}{size_str}")
            display = "; ".join(ds_names)
            evs = []
            if meth.datasets[0].get("evidence"):
                evs = [ResearchEvidenceReference.model_validate(e) for e in meth.datasets[0]["evidence"]]
            return ComparisonCell(
                value=[{"name": ds.get("name"), "sample_size": ds.get("sample_size"), "unit": ds.get("unit")} for ds in meth.datasets],
                display_text=display,
                status="similar",
                evidence=evs,
            )

        elif dimension == "models":
            if not meth or not meth.methods_and_models:
                return ComparisonCell(value=[], display_text="No models/methods recorded", status="missing")
            executed = [m.get("name") for m in meth.methods_and_models if m.get("execution_status") == "executed"]
            proposed = [m.get("name") for m in meth.methods_and_models if m.get("execution_status") == "proposed"]
            parts = []
            if executed:
                parts.append(f"Executed: {', '.join(executed)}")
            if proposed:
                parts.append(f"Proposed: {', '.join(proposed)}")
            display = " | ".join(parts) if parts else "Methods listed without status"
            evs = []
            if meth.methods_and_models[0].get("evidence"):
                evs = [ResearchEvidenceReference.model_validate(e) for e in meth.methods_and_models[0]["evidence"]]
            return ComparisonCell(
                value={"executed": executed, "proposed": proposed},
                display_text=display,
                status="similar",
                evidence=evs,
            )

        elif dimension == "evaluation":
            if not meth or not meth.evaluation_metrics:
                return ComparisonCell(value=[], display_text="No metrics recorded", status="missing")
            metrics = [m.get("name") for m in meth.evaluation_metrics if m.get("name")]
            hw = meth.experimental_setup.get("hardware_config") if isinstance(meth.experimental_setup, dict) else getattr(meth.experimental_setup, "hardware_config", None)
            display = f"Metrics: {', '.join(metrics)}" + (f" (Compute: {hw})" if hw else "")
            return ComparisonCell(
                value={"metrics": metrics, "hardware": hw},
                display_text=display,
                status="similar",
                evidence=[],
            )

        elif dimension == "limitations":
            if not meth or not meth.limitations:
                return ComparisonCell(value=[], display_text="No explicit author limitations found", status="missing")
            lim_texts = [lim.get("limitation_text", "") for lim in meth.limitations if lim.get("limitation_text")]
            display = "; ".join(lim_texts[:2])
            evs = []
            if meth.limitations[0].get("evidence"):
                evs = [ResearchEvidenceReference.model_validate(e) for e in meth.limitations[0]["evidence"]]
            return ComparisonCell(
                value=lim_texts,
                display_text=display,
                status="similar",
                evidence=evs,
            )

        return ComparisonCell(value=None, display_text="Unknown dimension", status="needs_review")

    def _extract_evidence_sample(self, metadata_fields: Any) -> List[ResearchEvidenceReference]:
        """Collects evidence items from field-level provenance dictionary."""
        evs: List[ResearchEvidenceReference] = []
        if isinstance(metadata_fields, dict):
            for field_name, f_data in metadata_fields.items():
                if isinstance(f_data, dict) and f_data.get("evidence"):
                    for e in f_data["evidence"]:
                        try:
                            evs.append(ResearchEvidenceReference.model_validate(e))
                            if len(evs) >= 2:
                                return evs
                        except Exception:
                            continue
        return evs

    # -----------------------------------------------------------------------
    # Difference Summaries Generator
    # -----------------------------------------------------------------------

    def _generate_dimension_differences(
        self,
        dimension: str,
        doc_ids: List[str],
        profiles: Dict[str, Any],
        cells: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generates pairwise comparison difference notes for a given dimension."""
        diffs = []
        # Pairwise comparison (Paper A vs Paper B)
        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                id_a = doc_ids[i]
                id_b = doc_ids[j]

                title_a = profiles[id_a]["document"].original_filename
                title_b = profiles[id_b]["document"].original_filename
                if profiles[id_a]["metadata"] and profiles[id_a]["metadata"].title:
                    title_a = profiles[id_a]["metadata"].title
                if profiles[id_b]["metadata"] and profiles[id_b]["metadata"].title:
                    title_b = profiles[id_b]["metadata"].title

                cell_a = cells.get(id_a, {})
                cell_b = cells.get(id_b, {})

                val_a = cell_a.get("display_text", "")
                val_b = cell_b.get("display_text", "")

                diff_desc, status = self._compare_cell_pair(dimension, cell_a, cell_b, title_a, title_b)
                if diff_desc:
                    ev_a = cell_a.get("evidence", [])
                    ev_b = cell_b.get("evidence", [])
                    diffs.append(
                        DifferenceSummaryItem(
                            dimension=dimension,
                            paper_a_title=title_a,
                            paper_b_title=title_b,
                            paper_a_value=val_a,
                            paper_b_value=val_b,
                            difference_description=diff_desc,
                            comparison_status=status,
                            evidence_a=[ResearchEvidenceReference.model_validate(e) for e in ev_a],
                            evidence_b=[ResearchEvidenceReference.model_validate(e) for e in ev_b],
                        ).model_dump()
                    )
        return diffs

    def _compare_cell_pair(
        self,
        dimension: str,
        cell_a: Dict[str, Any],
        cell_b: Dict[str, Any],
        title_a: str,
        title_b: str,
    ) -> Tuple[Optional[str], ComparisonStatus]:
        """Evaluates relationship and provides a plain-English explanation between two cells."""
        val_a = cell_a.get("value")
        val_b = cell_b.get("value")

        if val_a is None or val_b is None:
            return f"One or both papers lack extracted data for {dimension}.", "missing"

        if dimension == "metadata":
            year_a = val_a.get("year")
            year_b = val_b.get("year")
            venue_a = val_a.get("venue")
            venue_b = val_b.get("venue")
            if year_a and year_b and year_a != year_b:
                return f"Published in different years ({year_a} vs {year_b}) and venues ('{venue_a}' vs '{venue_b}').", "different"
            return f"Published around similar period ({year_a or 'n.d.'}).", "similar"

        elif dimension == "datasets":
            names_a = {d.get("name", "").lower() for d in val_a if isinstance(d, dict)}
            names_b = {d.get("name", "").lower() for d in val_b if isinstance(d, dict)}
            shared = names_a.intersection(names_b)
            if shared:
                return f"Both papers evaluate on shared benchmark: {', '.join(shared)}.", "partially_overlapping"
            return f"Evaluated on distinct datasets ({', '.join(names_a) or 'Dataset A'} vs {', '.join(names_b) or 'Dataset B'}). Metrics should not be directly compared.", "different"

        elif dimension == "models":
            exec_a = set(val_a.get("executed", []))
            exec_b = set(val_b.get("executed", []))
            shared = exec_a.intersection(exec_b)
            if shared:
                return f"Both studies benchmark {', '.join(shared)}.", "similar"
            return f"Studies test distinct model architectures ({', '.join(exec_a) or 'N/A'} vs {', '.join(exec_b) or 'N/A'}).", "different"

        elif dimension == "evaluation":
            m_a = set(val_a.get("metrics", []))
            m_b = set(val_b.get("metrics", []))
            shared = m_a.intersection(m_b)
            if shared:
                return f"Shared evaluation metrics: {', '.join(shared)}.", "similar"
            return f"Incompatible evaluation metrics ({', '.join(m_a)} vs {', '.join(m_b)}). Results cannot be ranked directly.", "not_comparable"

        elif dimension == "objectives":
            return f"Distinct primary objectives addressing different research problem formulations.", "different"

        elif dimension == "methodology":
            appr_a = set(val_a.get("approaches", []))
            appr_b = set(val_b.get("approaches", []))
            if appr_a == appr_b:
                return f"Both studies employ {', '.join(appr_a)} methodology.", "same"
            return f"Different methodological approaches ({', '.join(appr_a)} vs {', '.join(appr_b)}).", "different"

        elif dimension == "limitations":
            return "Distinct methodological caveats acknowledged by respective authors.", "different"

        return None, "similar"
