"""Dataset Validator for Query Intent Classification (Phase 5 C5.2).

Validates schema conformity, taxonomy referential integrity, duplicate records,
conflicting labels, and produces comprehensive statistical validation reports.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.ml.query_intent.taxonomy import (
    TAXONOMY_VERSION,
    TaxonomyRegistry,
)

VALID_SOURCE_TYPES: Set[str] = {
    "synthetic_seed",
    "manually_curated",
    "human_annotated",
    "anonymized_opt_in",
}

VALID_ANNOTATION_STATUSES: Set[str] = {
    "pending_human_review",
    "human_reviewed",
    "adjudicated",
}

VALID_SPLITS: Set[str] = {"train", "dev", "test"}


class DatasetValidationError(Exception):
    """Raised when query intent dataset fails structural or integrity validation."""

    def __init__(self, message: str, errors: Optional[List[str]] = None) -> None:
        super().__init__(message)
        self.errors = errors or []


@dataclass
class DatasetValidationReport:
    """Statistical summary and validation outcome for a query intent dataset."""

    total_examples: int
    examples_per_category: Dict[str, int]
    examples_per_split: Dict[str, int]
    category_distribution: Dict[str, float]
    duplicate_count: int
    conflicting_labels_count: int
    invalid_record_count: int
    unreviewed_example_count: int
    source_type_distribution: Dict[str, int]
    taxonomy_version: str
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes validation report to a plain dictionary."""
        return {
            "total_examples": self.total_examples,
            "examples_per_category": self.examples_per_category,
            "examples_per_split": self.examples_per_split,
            "category_distribution": self.category_distribution,
            "duplicate_count": self.duplicate_count,
            "conflicting_labels_count": self.conflicting_labels_count,
            "invalid_record_count": self.invalid_record_count,
            "unreviewed_example_count": self.unreviewed_example_count,
            "source_type_distribution": self.source_type_distribution,
            "taxonomy_version": self.taxonomy_version,
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class QueryIntentDatasetValidator:
    """Validates query intent dataset records against taxonomy rules and integrity invariants."""

    def __init__(self, expected_taxonomy_version: str = TAXONOMY_VERSION) -> None:
        self.expected_taxonomy_version = expected_taxonomy_version
        self.valid_categories = set(TaxonomyRegistry.list_category_ids())

    def validate_records(
        self,
        records: List[Dict[str, Any]],
        require_splits: bool = False,
        allow_warnings_as_errors: bool = False,
    ) -> DatasetValidationReport:
        """Validates an iterable of dataset records.

        Args:
            records: List of parsed JSON record dictionaries.
            require_splits: If True, every record must possess a valid 'split' field.
            allow_warnings_as_errors: If True, warnings are treated as validation errors.

        Returns:
            DatasetValidationReport containing distributions, counts, and errors.
        """
        errors: List[str] = []
        warnings: List[str] = []

        seen_ids: Set[str] = set()
        text_to_intents: Dict[str, Set[Tuple[str, str]]] = defaultdict(set)  # norm_text -> {(intent, example_id)}
        raw_text_counts: Counter = Counter()

        category_counts: Counter = Counter()
        split_counts: Counter = Counter()
        source_counts: Counter = Counter()
        status_counts: Counter = Counter()

        invalid_records = 0

        for idx, rec in enumerate(records):
            rec_id = rec.get("example_id")
            has_record_error = False

            # 1. Example ID validation
            if not rec_id or not isinstance(rec_id, str) or not rec_id.strip():
                errors.append(f"Record #{idx} missing valid non-empty 'example_id'.")
                has_record_error = True
            elif rec_id in seen_ids:
                errors.append(f"Duplicate example_id '{rec_id}' detected at record #{idx}.")
                has_record_error = True
            else:
                seen_ids.add(rec_id)

            # 2. Query text validation
            query_text = rec.get("query_text")
            if not query_text or not isinstance(query_text, str) or not query_text.strip():
                errors.append(f"Record '{rec_id or idx}' missing non-empty 'query_text'.")
                has_record_error = True
            else:
                cleaned_text = query_text.strip()
                raw_text_counts[cleaned_text] += 1
                norm_key = cleaned_text.lower()
                intent_val = str(rec.get("intent", ""))
                text_to_intents[norm_key].add((intent_val, rec_id or f"#{idx}"))

            # 3. Intent category validation
            intent = rec.get("intent")
            if not intent or intent not in self.valid_categories:
                errors.append(
                    f"Record '{rec_id or idx}' has invalid intent '{intent}'. "
                    f"Must be one of {sorted(self.valid_categories)}."
                )
                has_record_error = True
            else:
                category_counts[intent] += 1

            # 4. Attributes validation
            attrs = rec.get("attributes")
            if not isinstance(attrs, dict):
                errors.append(f"Record '{rec_id or idx}' 'attributes' must be a dictionary.")
                has_record_error = True
            else:
                expected_attr_keys = {
                    "requires_conversation_context",
                    "requires_multi_source_evidence",
                    "requests_explicit_citations",
                    "contains_ambiguous_reference",
                }
                for k in expected_attr_keys:
                    if k not in attrs or not isinstance(attrs[k], bool):
                        errors.append(
                            f"Record '{rec_id or idx}' attribute '{k}' must be a boolean."
                        )
                        has_record_error = True

            # 5. Source type validation
            source_type = rec.get("source_type")
            if not source_type or source_type not in VALID_SOURCE_TYPES:
                errors.append(
                    f"Record '{rec_id or idx}' has invalid source_type '{source_type}'. "
                    f"Must be one of {sorted(VALID_SOURCE_TYPES)}."
                )
                has_record_error = True
            else:
                source_counts[source_type] += 1

            # 6. Annotation status validation
            status = rec.get("annotation_status")
            if not status or status not in VALID_ANNOTATION_STATUSES:
                errors.append(
                    f"Record '{rec_id or idx}' has invalid annotation_status '{status}'. "
                    f"Must be one of {sorted(VALID_ANNOTATION_STATUSES)}."
                )
                has_record_error = True
            else:
                status_counts[status] += 1

            # 7. Taxonomy version validation
            tax_ver = rec.get("taxonomy_version")
            if tax_ver != self.expected_taxonomy_version:
                errors.append(
                    f"Record '{rec_id or idx}' taxonomy_version '{tax_ver}' does not match "
                    f"expected '{self.expected_taxonomy_version}'."
                )
                has_record_error = True

            # 8. Split validation
            split = rec.get("split")
            if split is not None:
                if split not in VALID_SPLITS:
                    errors.append(
                        f"Record '{rec_id or idx}' has invalid split '{split}'. "
                        f"Must be one of {sorted(VALID_SPLITS)}."
                    )
                    has_record_error = True
                else:
                    split_counts[split] += 1
            elif require_splits:
                errors.append(f"Record '{rec_id or idx}' missing required 'split' field.")
                has_record_error = True

            if has_record_error:
                invalid_records += 1

        # Check for duplicate raw text queries
        duplicate_queries = {text: count for text, count in raw_text_counts.items() if count > 1}
        duplicate_count = sum(duplicate_queries.values()) - len(duplicate_queries)
        if duplicate_count > 0:
            warnings.append(
                f"Detected {len(duplicate_queries)} queries with {duplicate_count} duplicate occurrences."
            )

        # Check for conflicting labels (same query text mapped to different intents)
        conflicts = {}
        for text, intents in text_to_intents.items():
            unique_intents = {item[0] for item in intents}
            if len(unique_intents) > 1:
                conflicts[text] = intents

        conflicting_count = len(conflicts)
        if conflicting_count > 0:
            for text, intent_pairs in conflicts.items():
                examples_str = ", ".join(f"{id_}: {int_}" for int_, id_ in intent_pairs)
                errors.append(
                    f"Conflicting intent labels for identical query '{text}': [{examples_str}]."
                )

        # Calculate category distribution
        total_valid_examples = len(records)
        cat_dist = {}
        for cat_id in sorted(self.valid_categories):
            count = category_counts.get(cat_id, 0)
            pct = (count / total_valid_examples * 100.0) if total_valid_examples > 0 else 0.0
            cat_dist[cat_id] = round(pct, 2)

        # Check for unrepresented categories
        missing_cats = [cat_id for cat_id in self.valid_categories if category_counts.get(cat_id, 0) == 0]
        if missing_cats:
            warnings.append(f"Taxonomy categories with zero examples: {missing_cats}")

        unreviewed_count = status_counts.get("pending_human_review", 0)

        if allow_warnings_as_errors and warnings:
            errors.extend(warnings)

        is_valid = len(errors) == 0

        return DatasetValidationReport(
            total_examples=total_valid_examples,
            examples_per_category={cat: category_counts.get(cat, 0) for cat in sorted(self.valid_categories)},
            examples_per_split=dict(split_counts),
            category_distribution=cat_dist,
            duplicate_count=duplicate_count,
            conflicting_labels_count=conflicting_count,
            invalid_record_count=invalid_records,
            unreviewed_example_count=unreviewed_count,
            source_type_distribution=dict(source_counts),
            taxonomy_version=self.expected_taxonomy_version,
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )
