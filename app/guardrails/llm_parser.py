"""Safe parsing of LLM text output into validated Pydantic models."""
import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n(.*)\n```$", re.DOTALL)


class LLMParseError(Exception):
    """Raised when LLM output cannot be parsed/validated into the expected schema."""


def parse_llm_output(raw: str, model_cls: type[T]) -> T:
    text = raw.strip()
    fence_match = _FENCE_RE.match(text)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMParseError(f"LLM output is not valid JSON: {exc}") from exc
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise LLMParseError(f"LLM output does not match schema {model_cls.__name__}: {exc}") from exc
