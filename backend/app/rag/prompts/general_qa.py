"""General Document Question Answering Prompt Renderer (Phase 3 C3.6)."""

import hashlib
from typing import List, Optional

from backend.app.llm.schemas import ChatMessage, MessageRole
from backend.app.rag.context.source_formatter import SourceFormatter
from backend.app.rag.prompts.exceptions import PromptRenderingError
from backend.app.rag.prompts.schemas import PromptInput, RenderedPrompt
from backend.app.rag.prompts.templates import (
    CORE_SYSTEM_PROMPT,
    STRUCTURED_OUTPUT_INSTRUCTION,
    USER_MESSAGE_TEMPLATE,
)
from backend.app.rag.prompts.version import PROMPT_VERSION


class GeneralQAPrompt:
    """Renders structured, evidence-grounded prompt bundles for general question answering."""

    def __init__(self, formatter: Optional[SourceFormatter] = None) -> None:
        self.formatter = formatter or SourceFormatter()
        self.version = PROMPT_VERSION

    def render(self, prompt_input: PromptInput) -> RenderedPrompt:
        """Renders prompt input into a verified, role-structured message list."""
        if not prompt_input.query or not prompt_input.query.strip():
            raise PromptRenderingError("Query cannot be empty for prompt rendering")

        # 1. Format evidence sources into delimited block
        formatted_evidence = self.formatter.format_all_sources(prompt_input.context_package.sources)

        # 2. Assemble system instructions
        system_instruction = f"{CORE_SYSTEM_PROMPT}\n\n{STRUCTURED_OUTPUT_INSTRUCTION}"

        # 3. Assemble user message safely without str.format() brace pitfalls
        user_message_content = (
            USER_MESSAGE_TEMPLATE
            .replace("{formatted_evidence}", formatted_evidence)
            .replace("{query}", prompt_input.query.strip())
        )

        messages: List[ChatMessage] = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_instruction)
        ]

        # 4. Include optional bounded conversation history
        if prompt_input.conversation_history:
            for hist_msg in prompt_input.conversation_history:
                # Disallow history from injecting system messages
                if hist_msg.role != MessageRole.SYSTEM:
                    messages.append(hist_msg)

        # 5. Append current turn user message
        messages.append(ChatMessage(role=MessageRole.USER, content=user_message_content))

        # Compute prompt hash for versioning and traceability
        combined_text = "\n".join([f"{m.role.value}:{m.content}" for m in messages])
        prompt_hash = hashlib.sha256(combined_text.encode("utf-8")).hexdigest()

        return RenderedPrompt(
            system_instruction=system_instruction,
            messages=messages,
            prompt_version=self.version,
            prompt_hash=prompt_hash,
            source_mapping=prompt_input.context_package.source_mapping,
        )
