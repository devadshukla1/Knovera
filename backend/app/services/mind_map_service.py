"""Mind Map Service for Knovera.

Constructs, merges, versions, and manages a unified workspace-wide Knovera Mind Map:
ROOT TOPIC -> PRIMARY TOPICS -> SECONDARY CONCEPTS -> DETAILED LEAF NODES.

Guarantees:
- Always uses ALL eligible, non-deleted, ready documents in the active workspace.
- Deduplicates and merges shared concepts across documents while preserving multi-source provenance.
- Preserves conflicting claims distinctly with source attribution.
- Tracks document collection fingerprints to detect out-of-date graphs on upload/deletion.
- Preserves learner mastery statuses across rebuilds and protects previous valid graphs on failure.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
import threading
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.logging import get_logger
from backend.app.llm.manager import LLMManager
from backend.app.llm.schemas import ChatMessage, LLMGenerationRequest, MessageRole
from backend.app.models.bkt import LearnerConceptMastery
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_graph_snapshot import KnowledgeGraphSnapshot
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.workspace import Workspace
from backend.app.repositories.knowledge_graph_snapshot_repository import (
    KnowledgeGraphSnapshotRepository,
)
from backend.app.schemas.knowledge_graph import (
    MindMapEdgeItem,
    MindMapNodeItem,
    MindMapTreeResponse,
)

logger = get_logger("knovera.services.mind_map")

_STOP_WORDS = {
    "a", "an", "the", "in", "on", "of", "for", "to", "with", "by", "and", "or",
    "using", "via", "from", "about", "overview", "introduction", "method", "approach",
}

# Distinguishing modifiers that must NEVER be merged even if remaining tokens overlap
_ANTONYM_OR_DISTINCT_MODIFIERS = [
    {"short", "long"},
    {"local", "global"},
    {"dense", "sparse"},
    {"supervised", "unsupervised"},
    {"static", "dynamic"},
    {"linear", "nonlinear"},
    {"internal", "external"},
    {"pros", "cons"},
    {"advantages", "limitations"},
    {"svm", "logistic", "forest", "kmeans", "bm25"},
    {"1", "2", "3", "4"},
]


def _normalize_label(label: str) -> str:
    """Canonical lowercase alphanumeric normalization for matching across versions."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (label or "").lower())).strip()


def _concept_tokens(label: str) -> Set[str]:
    """Extracts substantive tokens from a concept label for deduplication."""
    words = _normalize_label(label).split()
    return {w for w in words if w and w not in _STOP_WORDS}


def _are_concepts_equivalent(label_a: str, label_b: str) -> bool:
    """Determines if two concept labels represent the same canonical concept."""
    na = _normalize_label(label_a)
    nb = _normalize_label(label_b)
    if not na or not nb:
        return False
    if na == nb:
        return True

    ta = _concept_tokens(label_a)
    tb = _concept_tokens(label_b)
    if not ta or not tb:
        return False

    # Guard against merging genuinely distinct concepts with opposing modifiers
    for group in _ANTONYM_OR_DISTINCT_MODIFIERS:
        in_a = ta & group
        in_b = tb & group
        if in_a != in_b and (in_a or in_b):
            return False

    if ta == tb:
        return True

    intersection = len(ta & tb)
    union = len(ta | tb)
    jaccard = intersection / union if union else 0.0
    return jaccard >= 0.75 and intersection >= 2


class MindMapService:
    """Service orchestrating multi-document mind map synthesis, merging, and versioning."""

    _workspace_locks: Dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(self) -> None:
        self.settings = get_settings()

    @classmethod
    def _get_workspace_lock(cls, workspace_id: str) -> threading.Lock:
        with cls._locks_guard:
            if workspace_id not in cls._workspace_locks:
                cls._workspace_locks[workspace_id] = threading.Lock()
            return cls._workspace_locks[workspace_id]

    def _get_eligible_documents_and_fingerprint(
        self,
        workspace_id: uuid.UUID,
        session: Session,
    ) -> Tuple[List[Document], Dict[uuid.UUID, List[DocumentChunk]], str]:
        """Retrieves all ready, non-deleted workspace documents, their chunks, and a collection fingerprint."""
        documents = (
            session.query(Document)
            .filter(
                Document.workspace_id == workspace_id,
                Document.deleted_at.is_(None),
                Document.processing_status == "ready",
            )
            .order_by(Document.created_at.asc())
            .all()
        )

        doc_ids = [d.id for d in documents]
        chunks_by_doc: Dict[uuid.UUID, List[DocumentChunk]] = defaultdict(list)

        if doc_ids:
            all_chunks = (
                session.query(DocumentChunk)
                .filter(
                    DocumentChunk.workspace_id == workspace_id,
                    DocumentChunk.document_id.in_(doc_ids),
                )
                .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index.asc())
                .all()
            )
            for c in all_chunks:
                chunks_by_doc[c.document_id].append(c)

        fp_parts = []
        for d in documents:
            c_list = chunks_by_doc.get(d.id, [])
            fp_parts.append(
                f"{d.id}:{getattr(d, 'sha256', '') or ''}:{len(c_list)}"
            )
        fingerprint = hashlib.sha256("|".join(fp_parts).encode("utf-8")).hexdigest()[:16] if fp_parts else "empty"
        return documents, chunks_by_doc, fingerprint

    def get_mind_map(
        self,
        workspace_id: uuid.UUID,
        session: Session,
        user_id: Optional[uuid.UUID] = None,
        force_rebuild: bool = False,
    ) -> MindMapTreeResponse:
        """Retrieves cached mind map (marking out-of-date if documents changed) or builds a new one."""
        workspace = session.query(Workspace).filter(Workspace.id == workspace_id).first()
        if not workspace:
            raise ValueError(f"Workspace {workspace_id} not found")

        if force_rebuild:
            return self.build_mind_map(workspace_id, session, user_id=user_id)

        documents, chunks_by_doc, current_fp = self._get_eligible_documents_and_fingerprint(workspace_id, session)
        snap_repo = KnowledgeGraphSnapshotRepository(session)
        active_snapshot = snap_repo.get_active_snapshot(workspace_id)

        # If workspace has no ready documents, return empty state (never fabricate a graph)
        if not documents:
            return MindMapTreeResponse(
                workspace_id=str(workspace.id),
                workspace_name=workspace.name,
                root_node_id=f"root-{workspace.id}",
                nodes=[],
                edges=[],
                total_nodes=0,
                total_leaves=0,
                depth=4,
                version=0,
                source_document_ids=[],
                source_document_names=[],
                source_document_count=0,
                source_fingerprint="empty",
                is_out_of_date=False,
            )

        # Serve cached mind map if present and check freshness against current document fingerprint
        if active_snapshot and active_snapshot.graph_statistics:
            cached_tree = active_snapshot.graph_statistics.get("mind_map")
            if cached_tree and isinstance(cached_tree, dict) and len(cached_tree.get("nodes", [])) > 0:
                response = MindMapTreeResponse(**cached_tree)
                cached_fp = response.source_fingerprint
                if cached_fp != current_fp:
                    response.is_out_of_date = True
                    if len(documents) > (response.source_document_count or 0):
                        response.out_of_date_reason = "Out of date — New document available"
                    elif len(documents) < (response.source_document_count or 0):
                        response.out_of_date_reason = "Out of date — Document removed from workspace"
                    else:
                        response.out_of_date_reason = "Out of date — Workspace documents updated"
                else:
                    response.is_out_of_date = False
                    response.out_of_date_reason = None

                if user_id:
                    self._apply_user_mastery(response.nodes, workspace_id, user_id, session)
                return response

        # No cached tree yet -> build for the first time
        return self.build_mind_map(workspace_id, session, user_id=user_id)

    def build_mind_map(
        self,
        workspace_id: uuid.UUID,
        session: Session,
        user_id: Optional[uuid.UUID] = None,
    ) -> MindMapTreeResponse:
        """Rebuilds a unified 4-tier mind map from ALL eligible workspace documents."""
        lock = self._get_workspace_lock(str(workspace_id))
        with lock:
            workspace = session.query(Workspace).filter(Workspace.id == workspace_id).first()
            if not workspace:
                raise ValueError(f"Workspace {workspace_id} not found")

            documents, chunks_by_doc, current_fp = self._get_eligible_documents_and_fingerprint(workspace_id, session)

            snap_repo = KnowledgeGraphSnapshotRepository(session)
            active_snapshot = snap_repo.get_active_snapshot(workspace_id)

            # Capture previous version and learning statuses before rebuilding
            prev_version = 0
            prev_status_by_label: Dict[str, str] = {}
            prev_status_raw: List[Tuple[str, str]] = []
            if active_snapshot and active_snapshot.graph_statistics:
                prev_tree = active_snapshot.graph_statistics.get("mind_map")
                if isinstance(prev_tree, dict):
                    prev_version = int(prev_tree.get("version") or 0)
                    for n_dict in prev_tree.get("nodes", []):
                        st = n_dict.get("learning_status")
                        raw_lbl = n_dict.get("label", "")
                        lbl = _normalize_label(raw_lbl)
                        if lbl and st and st != "not_started":
                            prev_status_by_label[lbl] = st
                            prev_status_raw.append((raw_lbl, st))

            # If zero eligible documents remain (e.g. all deleted), return empty state and clear cache
            if not documents:
                empty_resp = MindMapTreeResponse(
                    workspace_id=str(workspace.id),
                    workspace_name=workspace.name,
                    root_node_id=f"root-{workspace.id}",
                    nodes=[],
                    edges=[],
                    total_nodes=0,
                    total_leaves=0,
                    depth=4,
                    version=prev_version + 1,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    source_document_ids=[],
                    source_document_names=[],
                    source_document_count=0,
                    source_fingerprint="empty",
                    is_out_of_date=False,
                )
                if active_snapshot:
                    stats = dict(active_snapshot.graph_statistics or {})
                    stats["mind_map"] = empty_resp.model_dump()
                    active_snapshot.graph_statistics = stats
                    session.commit()
                return empty_resp

            existing_nodes = (
                session.query(KnowledgeNode)
                .filter(KnowledgeNode.workspace_id == workspace_id)
                .all()
            )

            # Balanced sampling across EVERY eligible document
            sampled_by_doc = self._sample_balanced_chunks(documents, chunks_by_doc)
            total_sampled = sum(len(v) for v in sampled_by_doc.values())
            logger.info(
                "Building unified mind map for workspace '%s': %d eligible docs, %d sampled chunks",
                workspace.name,
                len(documents),
                total_sampled,
            )

            # 1. Attempt unified multi-document LLM synthesis
            tree_data = self._generate_with_llm(workspace, documents, sampled_by_doc, existing_nodes)

            # 2. Check document coverage & merge missing documents deterministically if needed
            if not tree_data or not tree_data.get("primary_topics"):
                logger.info("Using deterministic multi-document synthesis for workspace %s", workspace_id)
                per_doc_trees = [
                    self._generate_deterministic_for_doc(workspace, doc, chunks_by_doc.get(doc.id, []), existing_nodes)
                    for doc in documents
                ]
                tree_data = self._merge_cross_document_trees(workspace, per_doc_trees)
            else:
                # Verify every eligible document is represented; if any doc was missed by LLM, extract & merge it
                covered_docs = self._find_covered_document_names(tree_data)
                missing_docs = [
                    d for d in documents
                    if d.original_filename.lower() not in covered_docs
                ]
                if missing_docs:
                    logger.info(
                        "LLM omitted %d doc(s) (%s); synthesizing and merging them deterministically.",
                        len(missing_docs),
                        [d.original_filename for d in missing_docs],
                    )
                    extra_trees = [
                        self._generate_deterministic_for_doc(workspace, doc, chunks_by_doc.get(doc.id, []), existing_nodes)
                        for doc in missing_docs
                    ]
                    tree_data = self._merge_cross_document_trees(workspace, [tree_data] + extra_trees)
                else:
                    # Still run normalization & deduplication pass on LLM output
                    tree_data = self._merge_cross_document_trees(workspace, [tree_data])

            # 3. Assemble typed nodes and edges + validate before touching DB snapshot
            nodes, edges, merged_count = self._assemble_tree(workspace, tree_data, documents)
            if not nodes or not edges:
                raise RuntimeError("Generated mind map failed structural validation (empty nodes or edges).")

            # 4. Preserve learning status from previous version and BKT mastery table
            for node in nodes:
                if node.level == 0:
                    continue
                norm = _normalize_label(node.label)
                if norm in prev_status_by_label:
                    node.learning_status = prev_status_by_label[norm]
                else:
                    for prev_raw_lbl, prev_st in prev_status_raw:
                        if _are_concepts_equivalent(node.label, prev_raw_lbl):
                            node.learning_status = prev_st
                            break
            if user_id:
                self._apply_user_mastery(nodes, workspace_id, user_id, session)

            total_leaves = sum(1 for n in nodes if n.level == 3)
            root_id = nodes[0].id

            response = MindMapTreeResponse(
                workspace_id=str(workspace.id),
                workspace_name=workspace.name,
                root_node_id=root_id,
                nodes=nodes,
                edges=edges,
                total_nodes=len(nodes),
                total_leaves=total_leaves,
                depth=4,
                version=prev_version + 1,
                generated_at=datetime.now(timezone.utc).isoformat(),
                source_document_ids=[str(d.id) for d in documents],
                source_document_names=[d.original_filename for d in documents],
                source_document_count=len(documents),
                source_fingerprint=current_fp,
                is_out_of_date=False,
                out_of_date_reason=None,
                merged_concept_count=merged_count,
            )

            # 5. Atomic commit ONLY after full validation succeeds
            if not active_snapshot:
                active_snapshot = KnowledgeGraphSnapshot(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    status="completed",
                    is_active=True,
                    node_count=len(nodes),
                    edge_count=len(edges),
                    graph_statistics={"mind_map": response.model_dump()},
                )
                session.add(active_snapshot)
            else:
                stats = dict(active_snapshot.graph_statistics or {})
                stats["mind_map"] = response.model_dump()
                active_snapshot.graph_statistics = stats
                active_snapshot.node_count = len(nodes)
                active_snapshot.edge_count = len(edges)
            session.commit()

            return response

    def update_node_status(
        self,
        workspace_id: uuid.UUID,
        node_id: str,
        status: str,
        session: Session,
        user_id: uuid.UUID,
    ) -> MindMapNodeItem:
        """Updates learning status of a mind map node and updates active snapshot cache."""
        valid_statuses = {"not_started", "in_progress", "learned", "needs_revision"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status: {status}. Allowed: {valid_statuses}")

        snap_repo = KnowledgeGraphSnapshotRepository(session)
        active_snapshot = snap_repo.get_active_snapshot(workspace_id)
        target_node: Optional[MindMapNodeItem] = None

        if active_snapshot and active_snapshot.graph_statistics:
            import copy
            from sqlalchemy.orm.attributes import flag_modified
            stats = copy.deepcopy(active_snapshot.graph_statistics)
            cached_tree = stats.get("mind_map")
            if cached_tree and "nodes" in cached_tree:
                for n_dict in cached_tree["nodes"]:
                    if n_dict.get("id") == node_id:
                        n_dict["learning_status"] = status
                        target_node = MindMapNodeItem(**n_dict)
                        break
                active_snapshot.graph_statistics = stats
                flag_modified(active_snapshot, "graph_statistics")
                session.commit()

        # Update or create LearnerConceptMastery
        node_uuid = None
        try:
            node_uuid = uuid.UUID(node_id)
        except (ValueError, TypeError):
            if target_node:
                kn = (
                    session.query(KnowledgeNode)
                    .filter(
                        KnowledgeNode.workspace_id == workspace_id,
                        KnowledgeNode.name == target_node.label,
                    )
                    .first()
                )
                if kn:
                    node_uuid = kn.id

        if node_uuid:
            prob_map = {
                "not_started": 0.20,
                "in_progress": 0.55,
                "needs_revision": 0.40,
                "learned": 0.95,
            }
            mastery = (
                session.query(LearnerConceptMastery)
                .filter(
                    LearnerConceptMastery.workspace_id == workspace_id,
                    LearnerConceptMastery.concept_id == node_uuid,
                    LearnerConceptMastery.user_id == user_id,
                )
                .first()
            )
            prob = prob_map.get(status, 0.20)
            if not mastery:
                mastery = LearnerConceptMastery(
                    id=uuid.uuid4(),
                    workspace_id=workspace_id,
                    user_id=user_id,
                    concept_id=node_uuid,
                    posterior_mastery_probability=prob,
                    predicted_next_mastery_probability=prob,
                    observation_count=1,
                )
                session.add(mastery)
            else:
                mastery.posterior_mastery_probability = prob
                mastery.predicted_next_mastery_probability = prob
                mastery.observation_count += 1
            session.commit()

        if target_node:
            return target_node

        return MindMapNodeItem(
            id=node_id,
            label="Concept",
            level=2,
            node_type="secondary",
            learning_status=status,
        )

    # -------------------------------------------------------------------------
    # Private Helpers: Multi-Document Sampling, LLM Synthesis & Merging
    # -------------------------------------------------------------------------

    def _sample_balanced_chunks(
        self,
        documents: List[Document],
        chunks_by_doc: Dict[uuid.UUID, List[DocumentChunk]],
        total_budget: int = 24,
    ) -> Dict[uuid.UUID, List[DocumentChunk]]:
        """Samples chunks evenly across ALL eligible documents so no document is ignored."""
        if not documents:
            return {}
        per_doc_limit = max(3, min(8, total_budget // len(documents)))
        sampled: Dict[uuid.UUID, List[DocumentChunk]] = {}
        for doc in documents:
            doc_chunks = chunks_by_doc.get(doc.id, [])
            if len(doc_chunks) <= per_doc_limit:
                sampled[doc.id] = doc_chunks
            else:
                step = (len(doc_chunks) - 1) / (per_doc_limit - 1)
                indices = [round(i * step) for i in range(per_doc_limit)]
                sampled[doc.id] = [doc_chunks[idx] for idx in dict.fromkeys(indices)]
        return sampled

    def _apply_user_mastery(
        self,
        nodes: List[MindMapNodeItem],
        workspace_id: uuid.UUID,
        user_id: uuid.UUID,
        session: Session,
    ) -> None:
        """Applies user's Bayesian Knowledge Tracing status to matching nodes."""
        masteries = (
            session.query(LearnerConceptMastery)
            .filter(
                LearnerConceptMastery.workspace_id == workspace_id,
                LearnerConceptMastery.user_id == user_id,
            )
            .all()
        )
        if not masteries:
            return

        mastery_by_concept_id = {str(m.concept_id): m for m in masteries}
        kn_rows = session.query(KnowledgeNode.id, KnowledgeNode.name).filter(
            KnowledgeNode.workspace_id == workspace_id
        ).all()
        mastery_by_norm_name: Dict[str, Any] = {}
        for kn_id, kn_name in kn_rows:
            if str(kn_id) in mastery_by_concept_id:
                mastery_by_norm_name[_normalize_label(kn_name)] = mastery_by_concept_id[str(kn_id)]

        for node in nodes:
            m = mastery_by_concept_id.get(node.id) or mastery_by_norm_name.get(_normalize_label(node.label))
            if m:
                prob = m.posterior_mastery_probability
                if prob >= 0.85:
                    node.learning_status = "learned"
                elif prob >= 0.50:
                    node.learning_status = "in_progress"
                elif prob >= 0.30:
                    node.learning_status = "needs_revision"
                else:
                    node.learning_status = "not_started"

    def _generate_with_llm(
        self,
        workspace: Workspace,
        documents: List[Document],
        sampled_by_doc: Dict[uuid.UUID, List[DocumentChunk]],
        existing_nodes: List[KnowledgeNode],
    ) -> Optional[Dict[str, Any]]:
        """Invokes central Groq LLM to synthesize a unified multi-document 4-tier tree."""
        try:
            manager = LLMManager.get_instance()
            all_excerpts: List[str] = []
            for doc in documents:
                for c in sampled_by_doc.get(doc.id, []):
                    page_label = f"Page {c.page_start}" if c.page_start else f"Chunk {c.chunk_index + 1}"
                    all_excerpts.append(
                        f"[Document: {doc.original_filename} | {page_label}]: {c.content[:380]}"
                    )

            if not all_excerpts:
                return None

            doc_names = [d.original_filename for d in documents]
            context_text = "\n\n".join(all_excerpts)
            existing_concept_names = [n.name for n in existing_nodes[:20]]

            prompt = f"""You are an expert cognitive curriculum architect and multi-document knowledge graph engineer.
Analyze ALL {len(documents)} uploaded documents in workspace '{workspace.name}' and synthesize ONE unified 4-tier hierarchical Knovera Mind Map.

Eligible Documents ({len(documents)} total):
{json.dumps(doc_names)}

CRITICAL MULTI-DOCUMENT RULES:
1. You MUST incorporate concepts and facts from ALL {len(documents)} documents listed above. Never ignore any document.
2. Merge shared or equivalent concepts across documents into ONE canonical Secondary Concept node, listing ALL contributing documents and pages in "source_references".
3. Preserve unique concepts from each document under appropriate Primary Topics.
4. If two documents contain conflicting claims about a concept, keep both facts as separate leaf_nodes with their exact source_references and set "has_conflicting_info": true.
5. Structure:
   - ROOT (Level 0): Central theme of the workspace.
   - PRIMARY TOPICS (Level 1): 3 to 6 major domains spanning all documents.
   - SECONDARY CONCEPTS (Level 2): 2 to 5 key subtopics/methods/algorithms per primary topic.
   - LEAF NODES (Level 3): 2 to 4 grounded facts, definitions, formulas, or findings per secondary concept.

Existing detected concepts (reference if relevant):
{json.dumps(existing_concept_names)}

Document Excerpts:
{context_text}

Output MUST BE VALID JSON with no Markdown fences:
{{
  "root_label": "{workspace.name}",
  "root_description": "Unified knowledge mind map across {len(documents)} workspace document(s)",
  "primary_topics": [
    {{
      "label": "Primary Topic Name",
      "category": "Domain Category",
      "description": "Overview of this primary topic",
      "secondary_concepts": [
        {{
          "label": "Secondary Concept Name",
          "description": "Concise concept definition",
          "difficulty": "beginner|intermediate|advanced",
          "importance": "core|important|supplementary",
          "prerequisites": ["prerequisite concept name"],
          "has_conflicting_info": false,
          "source_references": [
            {{"document_title": "exact filename from list", "page_number": 1}}
          ],
          "leaf_nodes": [
            {{
              "label": "Concise Leaf Fact / Definition / Formula",
              "summary": "Detailed 1-2 sentence explanation grounded in the document.",
              "source_excerpt": "Relevant quote or context from document.",
              "source_references": [
                {{"document_title": "exact filename from list", "page_number": 1}}
              ]
            }}
          ]
        }}
      ]
    }}
  ]
}}"""

            effective_model = manager.get_active_model()
            messages = [
                ChatMessage(
                    role=MessageRole.SYSTEM,
                    content="You are a JSON-only API that outputs strictly valid JSON without markdown fences or additional commentary.",
                ),
                ChatMessage(role=MessageRole.USER, content=prompt),
            ]

            req = LLMGenerationRequest(
                model=effective_model,
                messages=messages,
                max_output_tokens=3500,
                temperature=0.2,
                response_format="json_object",
            )

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        response = pool.submit(asyncio.run, manager.generate_with_retry(req)).result()
                else:
                    response = loop.run_until_complete(manager.generate_with_retry(req))
            except RuntimeError:
                response = asyncio.run(manager.generate_with_retry(req))

            if not response or not response.content:
                return None

            clean_json = response.content.strip()
            if clean_json.startswith("```"):
                clean_json = re.sub(r"^```(?:json)?\n?", "", clean_json)
                clean_json = re.sub(r"\n?```$", "", clean_json)

            data = json.loads(clean_json)
            if "primary_topics" in data and len(data["primary_topics"]) > 0:
                logger.info(
                    "Groq LLM synthesized unified mind map: %d primary topics across %d doc(s)",
                    len(data["primary_topics"]),
                    len(documents),
                )
                return data
        except Exception as exc:
            logger.warning("LLM mind map generation failed (%s); using deterministic multi-doc fallback.", exc)
        return None

    def _find_covered_document_names(self, tree_data: Dict[str, Any]) -> Set[str]:
        """Collects lowercase document titles referenced anywhere in a raw tree_data dict."""
        covered: Set[str] = set()
        for p in tree_data.get("primary_topics", []):
            for s in p.get("secondary_concepts", []):
                for ref in s.get("source_references", []):
                    title = (ref.get("document_title") or "").strip().lower()
                    if title:
                        covered.add(title)
                for leaf in s.get("leaf_nodes", []):
                    for ref in leaf.get("source_references", []):
                        title = (ref.get("document_title") or "").strip().lower()
                        if title:
                            covered.add(title)
        return covered

    def _generate_deterministic_for_doc(
        self,
        workspace: Workspace,
        doc: Document,
        doc_chunks: List[DocumentChunk],
        existing_nodes: List[KnowledgeNode],
    ) -> Dict[str, Any]:
        """Deterministic, document-grounded extraction for a single document."""
        doc_title = doc.original_filename
        secondary_concepts: List[Dict[str, Any]] = []

        # Extract candidate concepts from chunks using headings / substantive phrases
        seen_labels: Set[str] = set()
        for idx, chunk in enumerate(doc_chunks[:8]):
            lines = [l.strip() for l in chunk.content.split("\n") if len(l.strip()) > 6]
            raw_heading = lines[0] if lines else f"Section {idx + 1}"
            # Clean heading to concise concept name
            concept_label = re.sub(r"^[0-9.\-:\s]+", "", raw_heading).strip()[:55]
            if not concept_label or len(concept_label) < 4:
                concept_label = f"{doc_title.rsplit('.', 1)[0]} — Part {idx + 1}"

            norm = _normalize_label(concept_label)
            if norm in seen_labels:
                continue
            seen_labels.add(norm)

            sentences = [s.strip() for s in re.split(r"[.!?]\s+", chunk.content) if len(s.strip()) > 20]
            leaf_nodes = []
            for sent in sentences[:3]:
                leaf_label = sent[:50] + ("..." if len(sent) > 50 else "")
                leaf_nodes.append({
                    "label": leaf_label,
                    "summary": sent,
                    "source_excerpt": sent,
                    "source_references": [{
                        "document_id": str(doc.id),
                        "document_title": doc_title,
                        "page_number": chunk.page_start,
                        "excerpt": sent[:180],
                    }],
                })
            if not leaf_nodes:
                leaf_nodes.append({
                    "label": f"Key Content ({doc_title})",
                    "summary": chunk.content[:240],
                    "source_excerpt": chunk.content[:200],
                    "source_references": [{
                        "document_id": str(doc.id),
                        "document_title": doc_title,
                        "page_number": chunk.page_start,
                        "excerpt": chunk.content[:180],
                    }],
                })

            secondary_concepts.append({
                "label": concept_label,
                "description": sentences[0] if sentences else chunk.content[:180],
                "difficulty": "intermediate",
                "importance": "core",
                "prerequisites": [],
                "has_conflicting_info": False,
                "source_references": [{
                    "document_id": str(doc.id),
                    "document_title": doc_title,
                    "page_number": chunk.page_start,
                }],
                "leaf_nodes": leaf_nodes,
            })

        base_topic = doc_title.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").strip()
        return {
            "root_label": workspace.name,
            "root_description": workspace.description or f"Unified mind map for {workspace.name}",
            "primary_topics": [{
                "label": f"{base_topic} Overview",
                "category": "Document Knowledge",
                "description": f"Core concepts extracted from {doc_title}.",
                "secondary_concepts": secondary_concepts[:5],
            }],
        }

    def _merge_cross_document_trees(
        self,
        workspace: Workspace,
        trees: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merges multiple trees, deduplicating equivalent primary topics & secondary concepts while keeping provenance."""
        merged_primaries: List[Dict[str, Any]] = []

        for tree in trees:
            for p in tree.get("primary_topics", []):
                p_label = (p.get("label") or "").strip()
                if not p_label:
                    continue

                # Find matching existing primary topic
                target_p = next(
                    (mp for mp in merged_primaries if _are_concepts_equivalent(mp["label"], p_label)),
                    None,
                )
                if not target_p:
                    target_p = {
                        "label": p_label,
                        "category": p.get("category") or "Domain",
                        "description": p.get("description") or "",
                        "secondary_concepts": [],
                    }
                    merged_primaries.append(target_p)

                for s in p.get("secondary_concepts", []):
                    s_label = (s.get("label") or "").strip()
                    if not s_label:
                        continue

                    # Search across ALL merged primaries to avoid duplicating the same concept under different branches
                    existing_s = None
                    for mp in merged_primaries:
                        existing_s = next(
                            (ms for ms in mp["secondary_concepts"] if _are_concepts_equivalent(ms["label"], s_label)),
                            None,
                        )
                        if existing_s:
                            break

                    if not existing_s:
                        target_p["secondary_concepts"].append({
                            "label": s_label,
                            "description": s.get("description") or "",
                            "difficulty": s.get("difficulty") or "intermediate",
                            "importance": s.get("importance") or "core",
                            "prerequisites": list(s.get("prerequisites") or []),
                            "has_conflicting_info": bool(s.get("has_conflicting_info", False)),
                            "source_references": list(s.get("source_references") or []),
                            "leaf_nodes": list(s.get("leaf_nodes") or []),
                        })
                    else:
                        # Merge provenance, complementary description, and unique leaf nodes
                        existing_refs = existing_s.setdefault("source_references", [])
                        seen_ref_keys = {
                            (r.get("document_title", "").lower(), r.get("page_number"))
                            for r in existing_refs
                        }
                        for ref in s.get("source_references") or []:
                            rk = (ref.get("document_title", "").lower(), ref.get("page_number"))
                            if rk not in seen_ref_keys:
                                existing_refs.append(ref)
                                seen_ref_keys.add(rk)

                        if s.get("has_conflicting_info"):
                            existing_s["has_conflicting_info"] = True

                        existing_leaves = existing_s.setdefault("leaf_nodes", [])
                        seen_leaf_norms = {_normalize_label(lf.get("label", "")) for lf in existing_leaves}
                        for lf in s.get("leaf_nodes") or []:
                            lnorm = _normalize_label(lf.get("label", ""))
                            if lnorm and lnorm not in seen_leaf_norms:
                                existing_leaves.append(lf)
                                seen_leaf_norms.add(lnorm)

        root_label = trees[0].get("root_label") if trees else workspace.name
        root_desc = trees[0].get("root_description") if trees else f"Unified knowledge mind map for {workspace.name}"
        return {
            "root_label": root_label or workspace.name,
            "root_description": root_desc or f"Unified knowledge mind map for {workspace.name}",
            "primary_topics": merged_primaries,
        }

    def _assemble_tree(
        self,
        workspace: Workspace,
        tree_data: Dict[str, Any],
        documents: List[Document],
    ) -> Tuple[List[MindMapNodeItem], List[MindMapEdgeItem], int]:
        """Assembles typed MindMapNodeItem and MindMapEdgeItem lists with multi-source provenance."""
        nodes: List[MindMapNodeItem] = []
        edges: List[MindMapEdgeItem] = []
        merged_count = 0

        doc_id_by_name = {d.original_filename.lower(): str(d.id) for d in documents}
        all_doc_names = [d.original_filename for d in documents]

        def _enrich_refs(raw_refs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
            enriched: List[Dict[str, Any]] = []
            doc_names: List[str] = []
            seen: Set[Tuple[str, Any]] = set()
            for r in raw_refs or []:
                title = (r.get("document_title") or "").strip()
                if not title:
                    continue
                page = r.get("page_number")
                key = (title.lower(), page)
                if key in seen:
                    continue
                seen.add(key)
                enriched.append({
                    "document_id": r.get("document_id") or doc_id_by_name.get(title.lower(), ""),
                    "document_title": title,
                    "page_number": page,
                    "excerpt": r.get("excerpt"),
                })
                if title not in doc_names:
                    doc_names.append(title)
            return enriched, doc_names

        # 1. Root Node (Level 0)
        root_id = f"root-{workspace.id}"
        root_label = tree_data.get("root_label") or workspace.name
        primary_list = tree_data.get("primary_topics", [])

        nodes.append(
            MindMapNodeItem(
                id=root_id,
                label=root_label,
                level=0,
                node_type="root",
                category="Root Subject",
                description=tree_data.get("root_description") or f"Unified knowledge map for {workspace.name}",
                children_count=len(primary_list),
                is_expanded=True,
                learning_status="in_progress",
                difficulty="beginner",
                importance="core",
                source_documents=all_doc_names,
            )
        )

        # 2. Primary Topics (Level 1)
        for p_idx, p_data in enumerate(primary_list):
            p_id = f"p-{p_idx}-{workspace.id}"
            p_label = p_data.get("label", f"Topic {p_idx + 1}")
            sec_list = p_data.get("secondary_concepts", [])

            p_doc_names: List[str] = []
            for s in sec_list:
                _, s_docs = _enrich_refs(s.get("source_references") or [])
                for dn in s_docs:
                    if dn not in p_doc_names:
                        p_doc_names.append(dn)

            nodes.append(
                MindMapNodeItem(
                    id=p_id,
                    label=p_label,
                    level=1,
                    node_type="primary",
                    category=p_data.get("category", "Domain"),
                    description=p_data.get("description"),
                    parent_id=root_id,
                    children_count=len(sec_list),
                    is_expanded=True,
                    learning_status="not_started",
                    difficulty="intermediate",
                    importance="core",
                    source_documents=p_doc_names or all_doc_names,
                )
            )
            edges.append(MindMapEdgeItem(id=f"edge-{root_id}-{p_id}", source=root_id, target=p_id))

            # 3. Secondary Concepts (Level 2)
            for s_idx, s_data in enumerate(sec_list):
                s_id = f"s-{p_idx}-{s_idx}-{workspace.id}"
                s_label = s_data.get("label", f"Concept {s_idx + 1}")
                leaf_list = s_data.get("leaf_nodes", [])

                s_refs, s_docs = _enrich_refs(s_data.get("source_references") or [])
                # Also collect refs from leaf nodes if secondary node lacked explicit refs
                for lf in leaf_list:
                    lf_refs, lf_docs = _enrich_refs(lf.get("source_references") or [])
                    for lr in lf_refs:
                        if not any(er["document_title"].lower() == lr["document_title"].lower() and er["page_number"] == lr["page_number"] for er in s_refs):
                            s_refs.append(lr)
                    for ld in lf_docs:
                        if ld not in s_docs:
                            s_docs.append(ld)

                is_shared = len({d.lower() for d in s_docs}) >= 2
                if is_shared:
                    merged_count += 1

                nodes.append(
                    MindMapNodeItem(
                        id=s_id,
                        label=s_label,
                        level=2,
                        node_type="secondary",
                        category=p_data.get("category"),
                        description=s_data.get("description"),
                        summary=s_data.get("description"),
                        parent_id=p_id,
                        children_count=len(leaf_list),
                        is_expanded=True,
                        learning_status="not_started",
                        difficulty=s_data.get("difficulty", "intermediate"),
                        importance=s_data.get("importance", "core"),
                        prerequisites=s_data.get("prerequisites", []),
                        source_documents=s_docs or all_doc_names,
                        source_references=s_refs,
                        source_page=s_refs[0]["page_number"] if s_refs else None,
                        is_shared_across_documents=is_shared,
                        has_conflicting_info=bool(s_data.get("has_conflicting_info", False)),
                    )
                )
                edges.append(MindMapEdgeItem(id=f"edge-{p_id}-{s_id}", source=p_id, target=s_id))

                # 4. Leaf Nodes (Level 3)
                for l_idx, l_data in enumerate(leaf_list):
                    l_id = f"l-{p_idx}-{s_idx}-{l_idx}-{workspace.id}"
                    l_label = l_data.get("label", f"Detail {l_idx + 1}")
                    l_refs, l_docs = _enrich_refs(l_data.get("source_references") or [])
                    if not l_refs and s_refs:
                        l_refs = s_refs[:1]
                        l_docs = [r["document_title"] for r in l_refs]

                    nodes.append(
                        MindMapNodeItem(
                            id=l_id,
                            label=l_label,
                            level=3,
                            node_type="leaf",
                            category="Fact / Detail",
                            description=l_data.get("summary"),
                            summary=l_data.get("summary"),
                            source_excerpt=l_data.get("source_excerpt"),
                            parent_id=s_id,
                            children_count=0,
                            is_expanded=False,
                            learning_status="not_started",
                            difficulty=s_data.get("difficulty", "intermediate"),
                            importance="supplementary",
                            source_documents=l_docs or s_docs or all_doc_names,
                            source_references=l_refs,
                            source_page=l_refs[0]["page_number"] if l_refs else None,
                        )
                    )
                    edges.append(MindMapEdgeItem(id=f"edge-{s_id}-{l_id}", source=s_id, target=l_id))

        return nodes, edges, merged_count
