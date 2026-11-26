"""Centralized Ontology Registry for Knovera Knowledge Graph (Phase 7 C7.1).

Defines authoritative concept categories, entity types, validation rules,
and semantic classifications for knowledge extraction.
"""

from enum import Enum
from typing import Dict, List, Optional, Set

ONTOLOGY_VERSION: str = "1.0.0"


class NodeType(str, Enum):
    """Broad classification of a knowledge graph node."""

    CONCEPT = "concept"
    ENTITY = "entity"


class ConceptType(str, Enum):
    """Abstract concepts, methods, processes, techniques, and properties."""

    THEORY = "theory"
    METHOD = "method"
    ALGORITHM = "algorithm"
    PROCESS = "process"
    TECHNICAL_CONCEPT = "technical_concept"
    RESEARCH_TOPIC = "research_topic"
    METRIC = "metric"
    PROPERTY = "property"
    PROBLEM = "problem"
    TECHNIQUE = "technique"


class EntityType(str, Enum):
    """Concrete or named referents, technologies, organizations, artifacts, etc."""

    PERSON = "person"
    ORGANIZATION = "organization"
    TECHNOLOGY = "technology"
    SOFTWARE = "software"
    PROGRAMMING_LANGUAGE = "programming_language"
    ALGORITHM = "algorithm"
    MODEL = "model"
    DATASET = "dataset"
    PUBLICATION = "publication"
    RESEARCH_PROJECT = "research_project"
    PRODUCT = "product"
    SYSTEM = "system"
    LOCATION = "location"
    EVENT = "event"
    OTHER = "other"


CONCEPT_TYPE_DESCRIPTIONS: Dict[ConceptType, str] = {
    ConceptType.THEORY: "Theoretical ideas, mathematical principles, and conceptual frameworks",
    ConceptType.METHOD: "Methodologies, analytical approaches, and systematic procedures",
    ConceptType.ALGORITHM: "Computational, numeric, and algorithmic step-by-step procedures",
    ConceptType.PROCESS: "Operations, pipelines, and sequential workflows",
    ConceptType.TECHNICAL_CONCEPT: "Domain-specific technical terminology, constructs, and properties",
    ConceptType.RESEARCH_TOPIC: "Academic subject areas, subfields, and research themes",
    ConceptType.METRIC: "Evaluation criteria, objective loss metrics, and quantitative measures",
    ConceptType.PROPERTY: "Characteristics, attributes, conditions, and system behaviors",
    ConceptType.PROBLEM: "Computational challenges, limitations, and open problem formulations",
    ConceptType.TECHNIQUE: "Practical implementation tricks, heuristics, and applied strategies",
}

ENTITY_TYPE_DESCRIPTIONS: Dict[EntityType, str] = {
    EntityType.PERSON: "Named individual, researcher, author, or creator",
    EntityType.ORGANIZATION: "Company, institution, university, research lab, or consortium",
    EntityType.TECHNOLOGY: "Underlying technology stack, protocol, hardware, or standard",
    EntityType.SOFTWARE: "Software library, application, tool, or runtime",
    EntityType.PROGRAMMING_LANGUAGE: "Programming or formal language specification",
    EntityType.ALGORITHM: "Specific named computational algorithm entity",
    EntityType.MODEL: "Named machine learning architecture, checkpoint, or model family",
    EntityType.DATASET: "Named corpus, benchmark dataset, or evaluation collection",
    EntityType.PUBLICATION: "Named academic paper, book, or technical report",
    EntityType.RESEARCH_PROJECT: "Named research initiative, grant, or open-source project",
    EntityType.PRODUCT: "Commercial or open-source branded software product",
    EntityType.SYSTEM: "Distributed architecture, database engine, or platform system",
    EntityType.LOCATION: "Physical location, country, or geographical entity",
    EntityType.EVENT: "Conference, workshop, benchmark competition, or release milestone",
    EntityType.OTHER: "Miscellaneous named real-world referent",
}

# Fast lookup sets
VALID_CONCEPT_TYPES: Set[str] = {c.value for c in ConceptType}
VALID_ENTITY_TYPES: Set[str] = {e.value for e in EntityType}
ALL_CATEGORIES: Set[str] = VALID_CONCEPT_TYPES | VALID_ENTITY_TYPES


def is_valid_concept_type(type_name: str) -> bool:
    """Checks whether a category string is an approved concept type."""
    return type_name.strip().lower() in VALID_CONCEPT_TYPES


def is_valid_entity_type(type_name: str) -> bool:
    """Checks whether a category string is an approved entity type."""
    return type_name.strip().lower() in VALID_ENTITY_TYPES


def is_valid_category(category_name: str) -> bool:
    """Checks whether a category string exists in the centralized ontology."""
    return category_name.strip().lower() in ALL_CATEGORIES


def infer_node_type(category_name: str) -> NodeType:
    """Infers whether an approved category belongs to Concept or Entity class."""
    cat = category_name.strip().lower()
    if cat in VALID_CONCEPT_TYPES and cat not in {EntityType.DATASET.value, EntityType.PERSON.value, EntityType.ORGANIZATION.value}:
        return NodeType.CONCEPT
    return NodeType.ENTITY


def get_category_description(category_name: str) -> Optional[str]:
    """Returns human-readable definition for an ontology category."""
    cat = category_name.strip().lower()
    for c_enum, desc in CONCEPT_TYPE_DESCRIPTIONS.items():
        if c_enum.value == cat:
            return desc
    for e_enum, desc in ENTITY_TYPE_DESCRIPTIONS.items():
        if e_enum.value == cat:
            return desc
    return None
