"""Knovera ORM models registry."""

from backend.app.models.user import User
from backend.app.models.workspace import Workspace
from backend.app.models.document import Document, DocumentPage
from backend.app.models.document_chunk import DocumentChunk
from backend.app.models.ingestion_job import IngestionJob
from backend.app.models.conversation import Conversation
from backend.app.models.message import Message
from backend.app.models.citation import Citation
from backend.app.models.topic_clustering_run import TopicClusteringRun
from backend.app.models.topic import Topic
from backend.app.models.topic_assignment import TopicAssignment
from backend.app.models.knowledge_extraction_run import KnowledgeExtractionRun
from backend.app.models.knowledge_node import KnowledgeNode
from backend.app.models.knowledge_mention import KnowledgeMention
from backend.app.models.knowledge_relationship import KnowledgeRelationship
from backend.app.models.relationship_evidence import RelationshipEvidence
from backend.app.models.knowledge_graph_snapshot import KnowledgeGraphSnapshot
from backend.app.models.study_material import (
    StudyMaterialGeneration,
    RevisionNote,
    MCQQuestion,
    MCQOption,
    FillBlankExercise,
    TrueFalseQuestion,
    Flashcard,
    QuizAttempt,
    QuizAttemptAnswer,
)
from backend.app.models.learner_intelligence import (
    QuestionConceptMapping,
    LearnerInteractionEvent,
    RevisionRecommendation,
)
from backend.app.models.bkt import (
    BKTModelVersion,
    BKTEstimationRun,
    BKTEvaluationRun,
    LearnerConceptMastery,
    LearnerConceptMasteryHistory,
)
from backend.app.models.research_intelligence import (
    ResearchAnalysisRun,
    ResearchMetadataProfile,
    ResearchObjectiveProfile,
    ResearchMethodologyProfile,
    ResearchComparisonProfile,
    ResearchFinding,
    ResearchFindingComparison,
    NLIInferenceRecord,
    NLIEvaluationRun,
    ResearchEvidenceValidationRecord,
    ResearchContradictionRecord,
    ResearchContradictionReview,
    DocumentCoverageAnalysisRun,
    DocumentCoverageGap,
)

__all__ = [
    "User",
    "Workspace",
    "Document",
    "DocumentPage",
    "DocumentChunk",
    "IngestionJob",
    "Conversation",
    "Message",
    "Citation",
    "TopicClusteringRun",
    "Topic",
    "TopicAssignment",
    "KnowledgeExtractionRun",
    "KnowledgeNode",
    "KnowledgeMention",
    "KnowledgeRelationship",
    "RelationshipEvidence",
    "KnowledgeGraphSnapshot",
    "StudyMaterialGeneration",
    "RevisionNote",
    "MCQQuestion",
    "MCQOption",
    "FillBlankExercise",
    "TrueFalseQuestion",
    "Flashcard",
    "QuizAttempt",
    "QuizAttemptAnswer",
    "QuestionConceptMapping",
    "LearnerInteractionEvent",
    "RevisionRecommendation",
    "BKTModelVersion",
    "BKTEstimationRun",
    "BKTEvaluationRun",
    "LearnerConceptMastery",
    "LearnerConceptMasteryHistory",
    "ResearchAnalysisRun",
    "ResearchMetadataProfile",
    "ResearchObjectiveProfile",
    "ResearchMethodologyProfile",
    "ResearchComparisonProfile",
    "ResearchFinding",
    "ResearchFindingComparison",
    "NLIInferenceRecord",
    "NLIEvaluationRun",
    "ResearchEvidenceValidationRecord",
    "ResearchContradictionRecord",
    "ResearchContradictionReview",
    "DocumentCoverageAnalysisRun",
    "DocumentCoverageGap",
]
