"""Relationship Ontology Registry for Knovera Knowledge Graph (Phase 7 C7.3).

Defines authoritative relationship predicates, category taxonomies,
directionality, symmetry, and inverse mapping semantics.
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

RELATIONSHIP_ONTOLOGY_VERSION: str = "1.0.0"


class RelationCategory(str, Enum):
    """Broad functional grouping of relationship predicates."""

    STRUCTURAL = "structural"
    FUNCTIONAL = "functional"
    PROVENANCE = "provenance"
    COMPARATIVE = "comparative"
    DATA_MODEL = "data_model"


class RelationPredicate(str, Enum):
    """Authoritative predicates for knowledge graph relationships."""

    # Structural / Hierarchical
    IS_A = "is_a"
    SUBCLASS_OF = "subclass_of"
    PART_OF = "part_of"
    CONTAINS = "contains"
    INSTANCE_OF = "instance_of"

    # Functional / Implementation
    USES = "uses"
    IMPLEMENTS = "implements"
    BASED_ON = "based_on"
    DEPENDS_ON = "depends_on"
    REQUIRES = "requires"
    PRODUCES = "produces"
    APPLIED_TO = "applied_to"
    SUPPORTS = "supports"

    # Provenance / Attribution
    PROPOSED_BY = "proposed_by"
    DEVELOPED_BY = "developed_by"
    INTRODUCED_BY = "introduced_by"
    EVALUATED_ON = "evaluated_on"
    COMPARED_WITH = "compared_with"
    CITED_BY = "cited_by"

    # Comparative / Evolution / Causality
    EXTENDS = "extends"
    IMPROVES = "improves"
    CAUSES = "causes"
    INFLUENCES = "influences"
    CONTRIBUTES_TO = "contributes_to"
    MEASURES = "measures"
    REDUCES = "reduces"
    INCREASES = "increases"

    # Data / Model specifics
    TRAINED_ON = "trained_on"
    TESTED_ON = "tested_on"
    EVALUATED_USING = "evaluated_using"
    CONTAINS_DATA_FROM = "contains_data_from"
    OUTPUTS = "outputs"
    PREDICTS = "predicts"


# Inverse predicate mappings (bi-directional semantic pairs)
INVERSE_PREDICATE_MAP: Dict[str, str] = {
    RelationPredicate.PART_OF.value: RelationPredicate.CONTAINS.value,
    RelationPredicate.CONTAINS.value: RelationPredicate.PART_OF.value,
    RelationPredicate.SUBCLASS_OF.value: "superclasses",
    RelationPredicate.INSTANCE_OF.value: "has_instance",
    RelationPredicate.USES.value: "used_by",
    RelationPredicate.IMPLEMENTS.value: "implemented_by",
    RelationPredicate.BASED_ON.value: "basis_for",
    RelationPredicate.DEPENDS_ON.value: "depended_on_by",
    RelationPredicate.REQUIRES.value: "required_by",
    RelationPredicate.PRODUCES.value: "produced_by",
    RelationPredicate.APPLIED_TO.value: "receives_application_of",
    RelationPredicate.SUPPORTS.value: "supported_by",
    RelationPredicate.PROPOSED_BY.value: "proposed",
    RelationPredicate.DEVELOPED_BY.value: "developed",
    RelationPredicate.INTRODUCED_BY.value: "introduced",
    RelationPredicate.EVALUATED_ON.value: "used_to_evaluate",
    RelationPredicate.EXTENDS.value: "extended_by",
    RelationPredicate.IMPROVES.value: "improved_by",
    RelationPredicate.CAUSES.value: "caused_by",
    RelationPredicate.MEASURES.value: "measured_by",
    RelationPredicate.TRAINED_ON.value: "trains_model",
    RelationPredicate.TESTED_ON.value: "tests_model",
    RelationPredicate.OUTPUTS.value: "output_of",
    RelationPredicate.PREDICTS.value: "predicted_by",
}

# Symmetric predicates where A rel B == B rel A
SYMMETRIC_PREDICATES: Set[str] = {
    RelationPredicate.COMPARED_WITH.value,
}

# Category classification mapping
PREDICATE_CATEGORIES: Dict[str, RelationCategory] = {
    RelationPredicate.IS_A.value: RelationCategory.STRUCTURAL,
    RelationPredicate.SUBCLASS_OF.value: RelationCategory.STRUCTURAL,
    RelationPredicate.PART_OF.value: RelationCategory.STRUCTURAL,
    RelationPredicate.CONTAINS.value: RelationCategory.STRUCTURAL,
    RelationPredicate.INSTANCE_OF.value: RelationCategory.STRUCTURAL,

    RelationPredicate.USES.value: RelationCategory.FUNCTIONAL,
    RelationPredicate.IMPLEMENTS.value: RelationCategory.FUNCTIONAL,
    RelationPredicate.BASED_ON.value: RelationCategory.FUNCTIONAL,
    RelationPredicate.DEPENDS_ON.value: RelationCategory.FUNCTIONAL,
    RelationPredicate.REQUIRES.value: RelationCategory.FUNCTIONAL,
    RelationPredicate.PRODUCES.value: RelationCategory.FUNCTIONAL,
    RelationPredicate.APPLIED_TO.value: RelationCategory.FUNCTIONAL,
    RelationPredicate.SUPPORTS.value: RelationCategory.FUNCTIONAL,

    RelationPredicate.PROPOSED_BY.value: RelationCategory.PROVENANCE,
    RelationPredicate.DEVELOPED_BY.value: RelationCategory.PROVENANCE,
    RelationPredicate.INTRODUCED_BY.value: RelationCategory.PROVENANCE,
    RelationPredicate.EVALUATED_ON.value: RelationCategory.PROVENANCE,
    RelationPredicate.COMPARED_WITH.value: RelationCategory.PROVENANCE,
    RelationPredicate.CITED_BY.value: RelationCategory.PROVENANCE,

    RelationPredicate.EXTENDS.value: RelationCategory.COMPARATIVE,
    RelationPredicate.IMPROVES.value: RelationCategory.COMPARATIVE,
    RelationPredicate.CAUSES.value: RelationCategory.COMPARATIVE,
    RelationPredicate.INFLUENCES.value: RelationCategory.COMPARATIVE,
    RelationPredicate.CONTRIBUTES_TO.value: RelationCategory.COMPARATIVE,
    RelationPredicate.MEASURES.value: RelationCategory.COMPARATIVE,
    RelationPredicate.REDUCES.value: RelationCategory.COMPARATIVE,
    RelationPredicate.INCREASES.value: RelationCategory.COMPARATIVE,

    RelationPredicate.TRAINED_ON.value: RelationCategory.DATA_MODEL,
    RelationPredicate.TESTED_ON.value: RelationCategory.DATA_MODEL,
    RelationPredicate.EVALUATED_USING.value: RelationCategory.DATA_MODEL,
    RelationPredicate.CONTAINS_DATA_FROM.value: RelationCategory.DATA_MODEL,
    RelationPredicate.OUTPUTS.value: RelationCategory.DATA_MODEL,
    RelationPredicate.PREDICTS.value: RelationCategory.DATA_MODEL,
}

ALL_PREDICATES: Set[str] = {p.value for p in RelationPredicate}

# Predicates that allow self-loops (A rel A). Empty by default for strictness.
ALLOWED_REFLEXIVE_PREDICATES: Set[str] = set()

# Domain (source node category) restrictions per predicate (empty set means any valid category allowed)
PREDICATE_DOMAIN_RESTRICTIONS: Dict[str, Set[str]] = {
    RelationPredicate.PROPOSED_BY.value: {"concept", "theory", "method", "algorithm", "model", "publication", "technical_concept"},
    RelationPredicate.DEVELOPED_BY.value: {"technology", "software", "model", "algorithm", "system", "product", "programming_language"},
    RelationPredicate.INTRODUCED_BY.value: {"concept", "theory", "method", "algorithm", "model", "publication", "technical_concept"},
    RelationPredicate.TRAINED_ON.value: {"model", "algorithm", "software"},
    RelationPredicate.TESTED_ON.value: {"model", "algorithm", "software", "method"},
    RelationPredicate.EVALUATED_ON.value: {"model", "algorithm", "software", "method", "system"},
    RelationPredicate.EVALUATED_USING.value: {"model", "algorithm", "software", "method"},
    RelationPredicate.MEASURES.value: {"metric"},
    RelationPredicate.OUTPUTS.value: {"model", "algorithm", "software", "process", "system"},
    RelationPredicate.PREDICTS.value: {"model", "algorithm", "software"},
}

# Range (target node category) restrictions per predicate (empty set means any valid category allowed)
PREDICATE_RANGE_RESTRICTIONS: Dict[str, Set[str]] = {
    RelationPredicate.PROPOSED_BY.value: {"person", "organization", "other"},
    RelationPredicate.DEVELOPED_BY.value: {"person", "organization", "other"},
    RelationPredicate.INTRODUCED_BY.value: {"person", "organization", "publication", "other"},
    RelationPredicate.TRAINED_ON.value: {"dataset"},
    RelationPredicate.TESTED_ON.value: {"dataset", "metric"},
    RelationPredicate.EVALUATED_ON.value: {"dataset", "metric"},
    RelationPredicate.EVALUATED_USING.value: {"metric", "method"},
    RelationPredicate.CITED_BY.value: {"publication", "research_project", "person"},
}


def is_valid_predicate(predicate_name: str) -> bool:
    """Checks whether a predicate string exists in the authoritative ontology."""
    return predicate_name.strip().lower() in ALL_PREDICATES


def is_symmetric_predicate(predicate_name: str) -> bool:
    """Checks whether the relationship is symmetric."""
    return predicate_name.strip().lower() in SYMMETRIC_PREDICATES


def is_allowed_self_loop(predicate_name: str) -> bool:
    """Checks whether self-loops (subject == object) are allowed for this predicate."""
    return predicate_name.strip().lower() in ALLOWED_REFLEXIVE_PREDICATES


def validate_predicate_domain_range(
    predicate_name: str,
    source_category: Optional[str],
    target_category: Optional[str],
) -> Tuple[bool, Optional[str]]:
    """Validates whether source and target categories satisfy domain/range restrictions."""
    pred = predicate_name.strip().lower()
    if pred not in ALL_PREDICATES:
        return False, f"Unknown predicate '{pred}'"

    if source_category:
        allowed_domains = PREDICATE_DOMAIN_RESTRICTIONS.get(pred)
        src_cat = source_category.strip().lower()
        if allowed_domains and src_cat not in allowed_domains:
            return False, f"Predicate '{pred}' does not permit source category '{src_cat}' (allowed: {sorted(list(allowed_domains))})"

    if target_category:
        allowed_ranges = PREDICATE_RANGE_RESTRICTIONS.get(pred)
        tgt_cat = target_category.strip().lower()
        if allowed_ranges and tgt_cat not in allowed_ranges:
            return False, f"Predicate '{pred}' does not permit target category '{tgt_cat}' (allowed: {sorted(list(allowed_ranges))})"

    return True, None


def get_inverse_predicate(predicate_name: str) -> Optional[str]:
    """Retrieves inverse predicate name if defined, else None."""
    pred = predicate_name.strip().lower()
    if pred in SYMMETRIC_PREDICATES:
        return pred
    return INVERSE_PREDICATE_MAP.get(pred)


def get_predicate_category(predicate_name: str) -> Optional[RelationCategory]:
    """Retrieves category for a given predicate."""
    return PREDICATE_CATEGORIES.get(predicate_name.strip().lower())
