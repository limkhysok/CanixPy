from __future__ import annotations


def pluralize(count: int, noun: str) -> str:
    """Format a count with its noun, appending "s" unless the count is 1."""
    return f"{count} {noun}{'s' if count != 1 else ''}"
