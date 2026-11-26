"""Central API router aggregating all v1 endpoint routers."""

from fastapi import APIRouter
from backend.app.api.v1.endpoints import (
    auth,
    bkt,
    citations,
    conversations,
    documents,
    health,
    knowledge_graph,
    learner_intelligence,
    learning_analytics,
    query_intent,
    recommendations,
    search,
    settings,
    study_materials,
    topics,
    workspaces,
)

api_router = APIRouter()

# Mount endpoint routers under /api/v1
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["Workspaces"])
api_router.include_router(documents.router, prefix="/workspaces", tags=["Documents"])
api_router.include_router(search.router, prefix="/workspaces", tags=["Search"])
api_router.include_router(conversations.router, tags=["Conversations"])
api_router.include_router(citations.router, prefix="/citations", tags=["Citations"])
api_router.include_router(query_intent.router, prefix="/query-intent", tags=["Query Intent"])
api_router.include_router(query_intent.router, prefix="/query/intent", tags=["Query Intent"])
api_router.include_router(topics.router, tags=["Topic Discovery"])
api_router.include_router(knowledge_graph.router, tags=["Knowledge Graph"])
api_router.include_router(study_materials.router, prefix="/workspaces", tags=["Study Materials"])
api_router.include_router(learner_intelligence.router, prefix="/workspaces", tags=["Learner Intelligence"])
api_router.include_router(bkt.router, prefix="/workspaces", tags=["Bayesian Knowledge Tracing"])
api_router.include_router(recommendations.router, prefix="/workspaces", tags=["Revision Recommendations"])
api_router.include_router(learning_analytics.router, prefix="/workspaces", tags=["Learning Analytics"])

