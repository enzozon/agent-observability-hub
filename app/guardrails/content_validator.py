"""Content validation applied before any agent acts on a piece of text."""

MAX_CONTENT_LENGTH = 10_000

BLOCKED_PATTERNS = (
    "ignore previous instructions",
    "ignore all previous",
    "disregard your instructions",
    "system prompt",
)


class ContentValidationError(Exception):
    """Raised when input content fails safety/sanity validation."""


def validate_content(text: str) -> str:
    if not text or not text.strip():
        raise ContentValidationError("Content is empty")
    if len(text) > MAX_CONTENT_LENGTH:
        raise ContentValidationError(f"Content exceeds {MAX_CONTENT_LENGTH} characters")
    lowered = text.lower()
    for pattern in BLOCKED_PATTERNS:
        if pattern in lowered:
            raise ContentValidationError(f"Blocked pattern detected: '{pattern}'")
    return text
