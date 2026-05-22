"""Small guardrail helpers for safe harness metadata handling."""

_SENSITIVE_KEY_PARTS = ("prompt", "answer", "submission", "content", "full_text")


def truncate_text(text: str, max_chars: int = 300) -> str:
    return text[:max_chars]


def safe_metadata(**kwargs) -> dict:
    return {
        key: value
        for key, value in kwargs.items()
        if not any(part in key.lower() for part in _SENSITIVE_KEY_PARTS)
    }
