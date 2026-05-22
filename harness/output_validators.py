"""Simple output validation helpers for future harness workflows."""


def is_non_empty_text(value: str) -> bool:
    return isinstance(value, str) and bool(value.strip())


def normalize_score(value) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None

    if 0 <= score <= 10:
        return score
    return None
