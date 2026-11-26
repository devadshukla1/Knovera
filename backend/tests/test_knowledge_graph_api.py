"""Comprehensive integration and unit test suite for Knowledge Graph API (Phase 7 C7.7)."""

from pathlib import Path
import tempfile
import uuid
import pytest

from backend.app.core.auth import create_access_token
from backend.app.ml.knowledge_graph.graph_builder import KnowledgeGraphBuilder
from backend.app.ml.knowledge_graph.graph_persistence import GraphPersistenceService
from backend.app.ml.knowledge_graph.ontology import ConceptType, EntityType
from backend.app.ml.knowledge_graph.schemas import (
    ExtractedRelationship,
    NormalizedNode,
)
from backend.app.models.document import Document
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.knowledge_mention import KnowledgeMention
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.knowledge_relationship import KnowledgeRelationship
from backend.app.models.relationship_evidence import RelationshipEvidence
from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.services.knowledge_graph_service import KnowledgeGraphService


@pytest.fixture
def auth_context(db_session):
    """Sets up an authenticated test user, workspace, and bearer token."""
    user = User(
        id=uuid.uuid4(),
        email=f"kg_test_{uuid.uuid4().hex[:6]}@knovera.test",
        password_hash="hashed_pw_test",
        display_name="Knowledge Graph Tester",
        status="active",
    )
    db_session.add(user)
    db_session.flush()

    workspace = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user.id,
        name="Knowledge Graph Workspace",
    )
    db_session.add(workspace)
    db_session.flush()

    token = create_access_token(user_id=str(user.id))
    headers = {"Authorization": f"Bearer {token}"}

    return {"user": user, "workspace": workspace, "headers": headers}


@pytest.fixture
def other_user_workspace(db_session):
    """Sets up a second user and workspace to test cross-tenant isolation."""
    user2 = User(
        id=uuid.uuid4(),
        email=f"kg_other_{uuid.uuid4().hex[:6]}@knovera.test",
        password_hash="hashed_pw_other",
        display_name="Other Tenant",
        status="active",
    )
    db_session.add(user2)
    db_session.flush()

    ws2 = Workspace(
        id=uuid.uuid4(),
        owner_user_id=user2.id,
        name="Other Tenant Workspace",
    )
    db_session.add(ws2)
    db_session.flush()

    return {"user": user2, "workspace": ws2}


@pytest.fixture
def seeded_knowledge_graph(db_session, auth_context):
    """Creates documents, chunks, nodes, relationships, evidence, and active snapshot."""
    user = auth_context["user"]
    ws = auth_context["workspace"]

    # 1. Document & Chunks
    doc = Document(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        uploaded_by_user_id=user.id,
        original_filename="deep_learning_foundations.pdf",
        storage_key=f"storage/{uuid.uuid4().hex}/doc.pdf",
        media_type="application/pdf",
        file_extension=".pdf",
        file_size_bytes=10240,
        sha256=uuid.uuid4().hex,
        processing_status="ready",
    )
    db_session.add(doc)
    db_session.flush()

    chunk1 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=0,
        content="Gradient Descent is an optimization algorithm that updates Model Parameters iteratively.",
        content_hash=uuid.uuid4().hex,
        page_start=12,
        page_end=12,
        parser_version="1.0.0",
        cleaning_version="1.0.0",
        chunking_version="1.0.0",
    )
    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        document_id=doc.id,
        chunk_index=1,
        content="Transformer models use Self-Attention mechanism and are trained on the Common Crawl dataset.",
        content_hash=uuid.uuid4().hex,
        page_start=15,
        page_end=16,
        parser_version="1.0.0",
        cleaning_version="1.0.0",
        chunking_version="1.0.0",
    )
    db_session.add_all([chunk1, chunk2])
    db_session.flush()

    # 2. Canonical Nodes
    n_gd = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        node_type="concept",
        category=ConceptType.ALGORITHM.value,
        name="Gradient Descent",
        normalized_name="gradient descent",
        description="Iterative first-order optimization algorithm.",
        aliases=["GD", "Steepest Descent"],
    )
    n_mp = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        node_type="concept",
        category=ConceptType.TECHNICAL_CONCEPT.value,
        name="Model Parameters",
        normalized_name="model parameters",
        description="Weights and biases of the neural model.",
        aliases=["Weights"],
    )
    n_tf = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        node_type="entity",
        category=EntityType.MODEL.value,
        name="Transformer",
        normalized_name="transformer",
        description="Attention-based neural network architecture.",
        aliases=["Transformer Architecture"],
    )
    n_sa = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        node_type="concept",
        category=ConceptType.METHOD.value,
        name="Self-Attention",
        normalized_name="self-attention",
        description="Mechanism relating different positions of a single sequence.",
        aliases=["Intra-Attention"],
    )
    n_cc = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        node_type="entity",
        category=EntityType.DATASET.value,
        name="Common Crawl",
        normalized_name="common crawl",
        description="Web crawl dataset.",
        aliases=["CC"],
    )
    # Isolated node
    n_iso = KnowledgeNode(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        node_type="concept",
        category=ConceptType.METRIC.value,
        name="Perplexity",
        normalized_name="perplexity",
        description="Measurement of how well a probability model predicts a sample.",
        aliases=["PPL"],
    )

    db_session.add_all([n_gd, n_mp, n_tf, n_sa, n_cc, n_iso])
    db_session.flush()

    # 3. Mentions
    m1 = KnowledgeMention(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        node_id=n_gd.id,
        chunk_id=chunk1.id,
        surface_form="Gradient Descent",
        start_offset=0,
        end_offset=16,
    )
    m2 = KnowledgeMention(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        node_id=n_mp.id,
        chunk_id=chunk1.id,
        surface_form="Model Parameters",
        start_offset=58,
        end_offset=74,
    )
    m3 = KnowledgeMention(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        node_id=n_tf.id,
        chunk_id=chunk2.id,
        surface_form="Transformer",
        start_offset=0,
        end_offset=11,
    )
    db_session.add_all([m1, m2, m3])
    db_session.flush()

    # 4. Relationships & Evidence
    rel1 = KnowledgeRelationship(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        source_node_id=n_gd.id,
        target_node_id=n_mp.id,
        relation_type="updates",
        is_negated=False,
        modality="certain",
        confidence=0.98,
        validation_status="validated",
    )
    rel1_parallel = KnowledgeRelationship(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        source_node_id=n_gd.id,
        target_node_id=n_mp.id,
        relation_type="optimizes",
        is_negated=False,
        modality="certain",
        confidence=0.95,
        validation_status="validated",
    )
    rel2 = KnowledgeRelationship(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        source_node_id=n_tf.id,
        target_node_id=n_sa.id,
        relation_type="uses",
        is_negated=False,
        modality="certain",
        confidence=0.99,
        validation_status="validated",
    )
    rel3 = KnowledgeRelationship(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        source_node_id=n_tf.id,
        target_node_id=n_cc.id,
        relation_type="trained_on",
        is_negated=False,
        modality="certain",
        confidence=0.92,
        validation_status="validated",
    )
    rel4 = KnowledgeRelationship(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        source_node_id=n_sa.id,
        target_node_id=n_mp.id,
        relation_type="optimizes",
        is_negated=False,
        modality="certain",
        confidence=0.90,
        validation_status="validated",
    )

    db_session.add_all([rel1, rel1_parallel, rel2, rel3, rel4])
    db_session.flush()

    ev1 = RelationshipEvidence(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        relationship_id=rel1.id,
        chunk_id=chunk1.id,
        evidence_text="Gradient Descent is an optimization algorithm that updates Model Parameters iteratively.",
        start_offset=0,
        end_offset=86,
    )
    ev2 = RelationshipEvidence(
        id=uuid.uuid4(),
        workspace_id=ws.id,
        relationship_id=rel2.id,
        chunk_id=chunk2.id,
        evidence_text="Transformer models use Self-Attention mechanism.",
        start_offset=0,
        end_offset=48,
    )
    db_session.add_all([ev1, ev2])
    db_session.flush()

    # 5. Persist Snapshot via GraphPersistenceService
    with tempfile.TemporaryDirectory() as tmp_dir:
        persistence = GraphPersistenceService(base_storage_dir=Path(tmp_dir))
        builder = KnowledgeGraphBuilder()

        schema_nodes = [
            NormalizedNode(
                id=str(n_gd.id),
                name=n_gd.name,
                normalized_name=n_gd.normalized_name,
                category=n_gd.category,
                node_type="concept",
                description=n_gd.description,
                aliases=n_gd.aliases,
                workspace_id=str(ws.id),
            ),
            NormalizedNode(
                id=str(n_mp.id),
                name=n_mp.name,
                normalized_name=n_mp.normalized_name,
                category=n_mp.category,
                node_type="concept",
                description=n_mp.description,
                aliases=n_mp.aliases,
                workspace_id=str(ws.id),
            ),
            NormalizedNode(
                id=str(n_tf.id),
                name=n_tf.name,
                normalized_name=n_tf.normalized_name,
                category=n_tf.category,
                node_type="entity",
                description=n_tf.description,
                aliases=n_tf.aliases,
                workspace_id=str(ws.id),
            ),
            NormalizedNode(
                id=str(n_sa.id),
                name=n_sa.name,
                normalized_name=n_sa.normalized_name,
                category=n_sa.category,
                node_type="concept",
                description=n_sa.description,
                aliases=n_sa.aliases,
                workspace_id=str(ws.id),
            ),
            NormalizedNode(
                id=str(n_cc.id),
                name=n_cc.name,
                normalized_name=n_cc.normalized_name,
                category=n_cc.category,
                node_type="entity",
                description=n_cc.description,
                aliases=n_cc.aliases,
                workspace_id=str(ws.id),
            ),
            NormalizedNode(
                id=str(n_iso.id),
                name=n_iso.name,
                normalized_name=n_iso.normalized_name,
                category=n_iso.category,
                node_type="concept",
                description=n_iso.description,
                aliases=n_iso.aliases,
                workspace_id=str(ws.id),
            ),
        ]

        schema_rels = [
            ExtractedRelationship(
                id=str(rel1.id),
                source_node_id=str(n_gd.id),
                target_node_id=str(n_mp.id),
                source_node_name=n_gd.name,
                target_node_name=n_mp.name,
                predicate="updates",
                confidence=0.98,
                validation_status="validated",
            ),
            ExtractedRelationship(
                id=str(rel1_parallel.id),
                source_node_id=str(n_gd.id),
                target_node_id=str(n_mp.id),
                source_node_name=n_gd.name,
                target_node_name=n_mp.name,
                predicate="optimizes",
                confidence=0.95,
                validation_status="validated",
            ),
            ExtractedRelationship(
                id=str(rel2.id),
                source_node_id=str(n_tf.id),
                target_node_id=str(n_sa.id),
                source_node_name=n_tf.name,
                target_node_name=n_sa.name,
                predicate="uses",
                confidence=0.99,
                validation_status="validated",
            ),
            ExtractedRelationship(
                id=str(rel3.id),
                source_node_id=str(n_tf.id),
                target_node_id=str(n_cc.id),
                source_node_name=n_tf.name,
                target_node_name=n_cc.name,
                predicate="trained_on",
                confidence=0.92,
                validation_status="validated",
            ),
            ExtractedRelationship(
                id=str(rel4.id),
                source_node_id=str(n_sa.id),
                target_node_id=str(n_mp.id),
                source_node_name=n_sa.name,
                target_node_name=n_mp.name,
                predicate="optimizes",
                confidence=0.90,
                validation_status="validated",
            ),
        ]

        graph, stats = builder.build_graph(str(ws.id), schema_nodes, schema_rels)
        snap, _ = persistence.persist_snapshot(
            workspace_id=str(ws.id),
            graph=graph,
            statistics=stats,
            session=db_session,
            is_active=True,
        )
        db_session.commit()

        # Clear in-memory cache to guarantee disk loading works
        KnowledgeGraphService.clear_cache()

        yield {
            "workspace": ws,
            "snapshot": snap,
            "nodes": [n_gd, n_mp, n_tf, n_sa, n_cc, n_iso],
            "relationships": [rel1, rel1_parallel, rel2, rel3, rel4],
            "evidence": [ev1, ev2],
            "document": doc,
        }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestKnowledgeGraphAPI:
    """Verifies all endpoints and security constraints of Knowledge Graph API."""

    def test_overview_empty_state_when_no_snapshot(self, test_client, auth_context):
        """Endpoint A returns empty state metadata when no snapshot exists yet."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]

        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["workspace_id"] == str(ws_id)
        assert data["has_graph"] is False
        assert data["snapshot"] is None
        assert data["capabilities"]["node_search"] is True

    def test_overview_with_active_snapshot(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint A returns active snapshot metadata, counts, and topological metrics."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]

        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_graph"] is True
        assert data["snapshot"]["is_active"] is True
        assert data["snapshot"]["node_count"] == 6
        assert data["snapshot"]["edge_count"] == 5
        assert data["snapshot"]["concept_count"] == 4
        assert data["snapshot"]["entity_count"] == 2
        assert data["statistics"]["isolated_node_count"] == 1
        assert "updates" in data["statistics"]["predicate_distribution"]

    def test_search_nodes_filtering_and_pagination(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint B searches nodes, filters by category/kind, and paginates."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]

        # 1. Search term match
        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph/nodes?search=gradient", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["label"] == "Gradient Descent"

        # 2. Search alias match
        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph/nodes?search=Steepest", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["label"] == "Gradient Descent"

        # 3. Filter by kind: entity
        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph/nodes?node_kind=entity", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        labels = {item["label"] for item in data["items"]}
        assert "Transformer" in labels
        assert "Common Crawl" in labels

        # 4. Filter by ontology category: algorithm
        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph/nodes?node_type=algorithm", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["label"] == "Gradient Descent"

        # 5. Pagination
        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph/nodes?page=1&page_size=3", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 6
        assert data["total_pages"] == 2

    def test_get_node_details(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint C retrieves full details and provenance for a single node."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]
        n_gd = seeded_knowledge_graph["nodes"][0]

        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph/nodes/{n_gd.id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["label"] == "Gradient Descent"
        assert data["node_kind"] == "concept"
        assert data["node_type"] == ConceptType.ALGORITHM.value
        assert data["out_degree"] == 2  # updates, optimizes
        assert data["mention_count"] == 1
        assert data["supporting_document_count"] == 1

    def test_get_neighborhood_expansion(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint D traverses bounded BFS subgraph and preserves parallel edges."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]
        n_gd = seeded_knowledge_graph["nodes"][0]

        # Depth 1 from Gradient Descent
        resp = test_client.get(
            f"/api/v1/workspaces/{ws_id}/knowledge-graph/neighborhood?node_id={n_gd.id}&depth=1",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["root_node_id"] == str(n_gd.id)
        assert data["total_nodes"] == 2  # Gradient Descent, Model Parameters
        assert data["total_edges"] == 2  # updates, optimizes (parallel edges preserved!)
        edge_preds = {e["predicate"] for e in data["edges"]}
        assert "updates" in edge_preds
        assert "optimizes" in edge_preds

    def test_get_neighborhood_with_pred_filter(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint D filters neighbors by relationship predicate."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]
        n_gd = seeded_knowledge_graph["nodes"][0]

        resp = test_client.get(
            f"/api/v1/workspaces/{ws_id}/knowledge-graph/neighborhood?node_id={n_gd.id}&depth=1&relationship_types=updates",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_edges"] == 1
        assert data["edges"][0]["predicate"] == "updates"

    def test_list_and_get_relationships(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoints E and F list filtered relationships and retrieve relationship details."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]
        rel1 = seeded_knowledge_graph["relationships"][0]

        # List
        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph/relationships?predicate=updates", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(rel1.id)

        # Single detail
        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph/relationships/{rel1.id}", headers=headers)
        assert resp.status_code == 200
        detail = resp.json()
        assert detail["id"] == str(rel1.id)
        assert detail["source_node_label"] == "Gradient Descent"
        assert detail["target_node_label"] == "Model Parameters"
        assert detail["predicate"] == "updates"
        assert detail["evidence_count"] >= 1

    def test_get_relationship_evidence(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint G retrieves source document excerpts and locations for relationship."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]
        rel1 = seeded_knowledge_graph["relationships"][0]

        resp = test_client.get(
            f"/api/v1/workspaces/{ws_id}/knowledge-graph/relationships/{rel1.id}/evidence",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        ev = data["items"][0]
        assert ev["document_title"] == "deep_learning_foundations.pdf"
        assert ev["page_start"] == 12
        assert "updates Model Parameters" in ev["evidence_text"]
        assert ev["is_source_available"] is True

    def test_get_node_evidence(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint H retrieves source document mentions supporting a node."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]
        n_gd = seeded_knowledge_graph["nodes"][0]

        resp = test_client.get(
            f"/api/v1/workspaces/{ws_id}/knowledge-graph/nodes/{n_gd.id}/evidence",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        mention = data["items"][0]
        assert mention["surface_form"] == "Gradient Descent"
        assert mention["document_title"] == "deep_learning_foundations.pdf"
        assert mention["page_start"] == 12
        assert mention["is_source_available"] is True

    def test_path_exploration(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint I explores connection paths between two canonical nodes."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]
        n_tf = seeded_knowledge_graph["nodes"][2]  # Transformer
        n_mp = seeded_knowledge_graph["nodes"][1]  # Model Parameters

        # Path: Transformer -> uses -> Self-Attention -> optimizes -> Model Parameters
        resp = test_client.get(
            f"/api/v1/workspaces/{ws_id}/knowledge-graph/paths?source_node_id={n_tf.id}&target_node_id={n_mp.id}&max_hops=3",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["no_path_found"] is False
        assert data["path_count"] >= 1
        path = data["paths"][0]
        assert path["hop_count"] == 2
        assert len(path["steps"]) == 2
        assert path["steps"][0]["edge"]["predicate"] == "uses"
        assert path["steps"][1]["edge"]["predicate"] == "optimizes"

    def test_path_exploration_no_path(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint I correctly reports no path when nodes are disconnected."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]
        n_tf = seeded_knowledge_graph["nodes"][2]
        n_iso = seeded_knowledge_graph["nodes"][5]  # Perplexity (isolated)

        resp = test_client.get(
            f"/api/v1/workspaces/{ws_id}/knowledge-graph/paths?source_node_id={n_tf.id}&target_node_id={n_iso.id}&max_hops=3",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["no_path_found"] is True
        assert data["path_count"] == 0

    def test_snapshot_history(self, test_client, auth_context, seeded_knowledge_graph):
        """Endpoint J lists historical graph snapshots for the workspace."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]

        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph/snapshots", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["items"][0]["is_active"] is True
        assert data["items"][0]["node_count"] == 6

    def test_cross_workspace_isolation_denied(self, test_client, auth_context, other_user_workspace, seeded_knowledge_graph):
        """Security invariant: authenticated users cannot access graph data of another workspace."""
        other_ws = other_user_workspace["workspace"]
        headers = auth_context["headers"]  # Authenticated as user 1

        # Attempting to access User 2's workspace returns 404 (non-disclosing)
        resp = test_client.get(f"/api/v1/workspaces/{other_ws.id}/knowledge-graph", headers=headers)
        assert resp.status_code == 404

        resp = test_client.get(f"/api/v1/workspaces/{other_ws.id}/knowledge-graph/nodes", headers=headers)
        assert resp.status_code == 404

        resp = test_client.get(f"/api/v1/workspaces/{other_ws.id}/knowledge-graph/relationships", headers=headers)
        assert resp.status_code == 404

    def test_unauthenticated_request_succeeds_in_local_mode(self, test_client, auth_context):
        """In local single-user mode, unauthenticated requests succeed."""
        ws_id = auth_context["workspace"].id
        resp = test_client.get(f"/api/v1/workspaces/{ws_id}/knowledge-graph")
        assert resp.status_code == 200

    def test_build_knowledge_graph_and_node_learning_status(self, test_client, auth_context, seeded_knowledge_graph):
        """Tests building the knowledge graph and updating persistent learning statuses."""
        ws_id = auth_context["workspace"].id
        headers = auth_context["headers"]
        node = seeded_knowledge_graph["nodes"][0]

        # 1. Test update node learning status
        status_resp = test_client.patch(
            f"/api/v1/workspaces/{ws_id}/knowledge-graph/nodes/{node.id}/status",
            json={"status": "learned"},
            headers=headers,
        )
        assert status_resp.status_code == 200
        data = status_resp.json()
        assert data["learning_status"] == "learned"

        # 2. Update to needs_revision
        status_resp2 = test_client.patch(
            f"/api/v1/workspaces/{ws_id}/knowledge-graph/nodes/{node.id}/status",
            json={"status": "needs_revision"},
            headers=headers,
        )
        assert status_resp2.status_code == 200
        assert status_resp2.json()["learning_status"] == "needs_revision"

        # 3. Test build graph endpoint with document chunks
        build_resp = test_client.post(
            f"/api/v1/workspaces/{ws_id}/knowledge-graph/build",
            headers=headers,
        )
        assert build_resp.status_code == 201
        build_data = build_resp.json()
        assert build_data["has_graph"] is True
        assert build_data["snapshot"]["node_count"] > 0
