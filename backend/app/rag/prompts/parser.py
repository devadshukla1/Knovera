"""Structured Output Parser for LLM Generation Responses (Phase 3 C3.6)."""

import json
import re
from typing import Any, Dict, Optional, Set

from pydantic import ValidationError

from backend.app.rag.prompts.exceptions import StructuredOutputParseError
from backend.app.rag.prompts.schemas import StructuredAnswerDraft


class StructuredOutputParser:
    """Parses and validates LLM generation output into verified StructuredAnswerDraft."""

    def __init__(self, allow_fallback_text_draft: bool = False) -> None:
        self.allow_fallback = allow_fallback_text_draft

    def _extract_json_string(self, raw_text: str) -> str:
        """Extracts JSON substring, stripping markdown fences if present."""
        clean = raw_text.strip()

        # Handle ```json ... ``` markdown fence
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
        if match:
            return match.group(1).strip()

        # Handle raw JSON with surrounding prose
        first_brace = clean.find("{")
        last_brace = clean.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return clean[first_brace : last_brace + 1].strip()

        return clean

    def parse(
        self,
        raw_completion: str,
        valid_source_ids: Optional[Set[str]] = None,
    ) -> StructuredAnswerDraft:
        """Parses raw completion text into validated StructuredAnswerDraft.

        Args:
            raw_completion: Output string returned by LLM provider.
            valid_source_ids: Optional set of allowed prompt-local source IDs (e.g. {'S1', 'S2'}).

        Raises:
            StructuredOutputParseError: If text cannot be parsed or validated against schema.
        """
        if not raw_completion or not raw_completion.strip():
            raise StructuredOutputParseError("Cannot parse empty completion from LLM")

        json_str = self._extract_json_string(raw_completion)

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            if self.allow_fallback:
                # Fallback text draft if configured
                return StructuredAnswerDraft(
                    answer=raw_completion.strip(),
                    claims=[],
                    limitations=["Response was not formatted in structured JSON"],
                    insufficient_evidence=False,
                )
            raise StructuredOutputParseError(f"Failed to decode JSON from completion: {exc}") from exc

        if not isinstance(data, dict):
            raise StructuredOutputParseError(f"Expected JSON object (dict), got {type(data).__name__}")

        try:
            draft = StructuredAnswerDraft.model_validate(data)
        except ValidationError as exc:
            raise StructuredOutputParseError(f"Validation against StructuredAnswerDraft failed: {exc}") from exc

        # Source ID validation against valid_source_ids
        if valid_source_ids is not None:
            sanitized_claims = []
            for claim in draft.claims:
                valid_ids = [sid for sid in claim.source_ids if sid in valid_source_ids]
                invalid_ids = [sid for sid in claim.source_ids if sid not in valid_source_ids]

                if invalid_ids:
                    draft.limitations.append(f"Model cited unknown source ID(s) {invalid_ids} for claim: '{claim.text[:40]}...'")

                sanitized_claims.append(claim.model_copy(update={"source_ids": valid_ids}))

            draft = draft.model_copy(update={"claims": sanitized_claims})

        # Insufficient evidence consistency
        if draft.insufficient_evidence and draft.claims:
            draft = draft.model_copy(update={"claims": []})

        return draft
