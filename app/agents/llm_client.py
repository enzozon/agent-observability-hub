"""LLM client protocol and the deterministic stub used by default (no API key needed)."""
import json
from typing import Protocol

DRAFT_MARKER = "DRAFT:"


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...


class StubLLMClient:
    """Deterministic client: returns the draft embedded in the prompt as valid JSON.

    Swap for a real Anthropic/OpenAI client in production; the writer agent only
    depends on the `complete(prompt) -> str` protocol.
    """

    def complete(self, prompt: str) -> str:
        marker_pos = prompt.rfind(DRAFT_MARKER)
        if marker_pos == -1:
            return json.dumps({"report": ""})
        draft = prompt[marker_pos + len(DRAFT_MARKER):].strip()
        return json.dumps({"report": draft}, ensure_ascii=False)
