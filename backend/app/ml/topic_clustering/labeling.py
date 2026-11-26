"""Cluster Labelling Service for Knovera Topic Discovery (Phase 6 C6.5)."""

import json
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.llm.schemas import ChatMessage, LLMGenerationRequest, MessageRole
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.ml.topic_clustering.keyword_extraction import ClusterKeywordExtractor
from backend.app.ml.topic_clustering.schemas import (
    ClusterAssignment,
    ClusterStats,
    TopicKeyword,
    TopicLabelMetadata,
)

logger = get_logger("knovera.ml.topic_clustering.labeling")


class ClusterLabelingService:
    """Generates grounded topic labels from canonical chunk text using keyword extraction and optional LLM assistance."""

    def __init__(
        self,
        keyword_extractor: Optional[ClusterKeywordExtractor] = None,
        llm_manager: Optional[LLMManager] = None,
    ) -> None:
        self.settings = get_settings()
        self.keyword_extractor = keyword_extractor or ClusterKeywordExtractor(
            top_k=self.settings.TOPIC_LABEL_KEYWORD_COUNT
        )
        self.llm_manager = llm_manager or (
            LLMManager.get_instance() if self.settings.TOPIC_ENABLE_LLM_LABELING else None
        )

    def hydrate_canonical_chunks(
        self,
        session: Session,
        workspace_id: uuid.UUID,
        chunk_ids: List[str],
    ) -> Dict[str, DocumentChunk]:
        """Fetches canonical chunk records from PostgreSQL for the authorized workspace.

        Strictly filters out soft-deleted documents.
        """
        if not chunk_ids:
            return {}

        parsed_uuids = []
        for cid in chunk_ids:
            try:
                parsed_uuids.append(uuid.UUID(cid))
            except ValueError:
                continue

        stmt = (
            select(DocumentChunk)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(
                DocumentChunk.id.in_(parsed_uuids),
                DocumentChunk.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
            )
        )
        results = session.execute(stmt).scalars().all()
        return {str(c.id): c for c in results}

    def generate_deterministic_label(
        self,
        keywords: List[TopicKeyword],
        cluster_id: int,
    ) -> Tuple[str, str]:
        """Composes a concise, professional title and description from top distinctive keywords."""
        if not keywords:
            return (
                f"Mixed Topic Cluster {cluster_id}",
                "Cluster contains diverse or weakly separated concepts.",
            )

        # Pick top 2-3 keywords that are not sub-strings of each other
        chosen_terms: List[str] = []
        for kw in keywords[:5]:
            t_clean = kw.term.strip()
            # Avoid duplicate or subphrase overlap
            if not any(t_clean.lower() in existing.lower() for existing in chosen_terms):
                chosen_terms.append(t_clean.title())
            if len(chosen_terms) >= 3:
                break

        if not chosen_terms:
            title = f"Topic Cluster {cluster_id}"
        elif len(chosen_terms) == 1:
            title = chosen_terms[0]
        elif len(chosen_terms) == 2:
            title = f"{chosen_terms[0]} & {chosen_terms[1]}"
        else:
            title = f"{chosen_terms[0]}, {chosen_terms[1]} & {chosen_terms[2]}"

        keyword_list_str = ", ".join(kw.term for kw in keywords[:6])
        description = f"Focuses on {keyword_list_str}."

        return title, description

    async def generate_llm_assisted_label(
        self,
        cluster_id: int,
        keywords: List[TopicKeyword],
        representative_excerpts: List[str],
    ) -> Optional[Tuple[str, str]]:
        """Optional LLM-assisted label generation with strict schema validation and fallback."""
        if not self.llm_manager:
            return None

        kw_str = ", ".join(kw.term for kw in keywords[:8])
        excerpts_str = "\n".join(
            f"- {e[:150]}..." for e in representative_excerpts[:3]
        )

        prompt = f"""You are a scientific taxonomy expert. Summarize this document cluster into a concise topic label (2-5 words) and a 1-sentence description.
Strict requirement: You MUST return a JSON object with keys "label" and "description". Do not invent unsupported concepts.

Top Keywords: {kw_str}
Representative Excerpts:
{excerpts_str}
"""
        try:
            req = LLMGenerationRequest(
                model=self.settings.LLM_MODEL,
                messages=[ChatMessage(role=MessageRole.USER, content=prompt)],
                temperature=0.2,
                max_output_tokens=150,
            )
            resp = await self.llm_manager.generate(req)
            content = resp.content.strip()

            # Strip markdown json blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            parsed = json.loads(content)
            label = parsed.get("label", "").strip()
            desc = parsed.get("description", "").strip()

            if label and len(label) <= 100:
                logger.info("LLM-assisted labelling succeeded for cluster %d: '%s'", cluster_id, label)
                return label, desc

        except Exception as exc:
            logger.warning("LLM labelling failed for cluster %d: %s; falling back to deterministic.", cluster_id, exc)

        return None

    def label_clusters(
        self,
        session: Session,
        workspace_id: uuid.UUID,
        assignments: List[ClusterAssignment],
        cluster_stats: Dict[int, ClusterStats],
        existing_topic_labels: Optional[Dict[str, TopicLabelMetadata]] = None,
    ) -> Dict[int, TopicLabelMetadata]:
        """Generates grounded TopicLabelMetadata for all discovered clusters.

        Preserves any existing human_reviewed or approved labels for matching cluster keys.
        """
        all_chunk_ids = [a.chunk_id for a in assignments]
        chunk_map = self.hydrate_canonical_chunks(session, workspace_id, all_chunk_ids)

        # Group canonical chunk texts and documents by cluster
        cluster_texts: Dict[int, List[str]] = {cid: [] for cid in cluster_stats.keys()}
        cluster_doc_ids: Dict[int, Set[str]] = {cid: set() for cid in cluster_stats.keys()}

        for a in assignments:
            c = chunk_map.get(a.chunk_id)
            if c:
                cluster_texts[a.cluster_id].append(c.content)
                cluster_doc_ids[a.cluster_id].add(str(c.document_id))

        # 1. Extract keywords per cluster
        keywords_by_cluster = self.keyword_extractor.extract_cluster_keywords(cluster_texts)

        topic_metadata_map: Dict[int, TopicLabelMetadata] = {}

        for cid, stats in cluster_stats.items():
            cluster_key = f"cluster_{cid}"
            keywords = keywords_by_cluster.get(cid, [])
            rep_chunk_ids = stats.representative_chunk_ids
            doc_count = len(cluster_doc_ids.get(cid, set()))
            chunk_count = stats.size

            # Check if this cluster key already has a human-approved label to preserve
            if (
                existing_topic_labels
                and cluster_key in existing_topic_labels
                and existing_topic_labels[cluster_key].label_status in ("reviewed", "approved")
            ):
                preserved = existing_topic_labels[cluster_key]
                logger.info(
                    "Preserving human-approved label '%s' for %s",
                    preserved.label,
                    cluster_key,
                )
                topic_metadata_map[cid] = TopicLabelMetadata(
                    cluster_key=cluster_key,
                    cluster_id=cid,
                    label=preserved.label,
                    description=preserved.description,
                    label_source=preserved.label_source,
                    label_status=preserved.label_status,
                    keywords=keywords,
                    representative_chunk_ids=rep_chunk_ids,
                    supporting_document_count=doc_count,
                    supporting_chunk_count=chunk_count,
                    cluster_statistics=stats.model_dump(),
                )
                continue

            # Deterministic label generation
            label, description = self.generate_deterministic_label(keywords, cid)
            label_source = "keyword_based"
            label_status = "suggested" if keywords else "needs_review"

            topic_metadata_map[cid] = TopicLabelMetadata(
                cluster_key=cluster_key,
                cluster_id=cid,
                label=label,
                description=description,
                label_source=label_source,
                label_status=label_status,
                keywords=keywords,
                representative_chunk_ids=rep_chunk_ids,
                supporting_document_count=doc_count,
                supporting_chunk_count=chunk_count,
                cluster_statistics=stats.model_dump(),
            )

        return topic_metadata_map
