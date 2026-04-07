"""Heuristic token estimation utilities."""

from __future__ import annotations

from typing import Any
import json


def estimate_text_tokens(text: str) -> int:
    """Estimates tokens using the documented four-characters rule.

    Args:
        text: Source text.

    Returns:
        Estimated token count.
    """

    if text == "":
        return 0
    return (len(text) + 3) // 4


def estimate_item_tokens(item: dict[str, Any]) -> int:
    """Estimates token count for a single JSON-like item.

    Args:
        item: Item to estimate.

    Returns:
        Estimated token count.
    """

    serialized: str = json.dumps(item, ensure_ascii=False)
    return estimate_text_tokens(text=serialized)


def estimate_items_tokens(items: list[dict[str, Any]]) -> int:
    """Estimates token count for a list of items.

    Args:
        items: Items to estimate.

    Returns:
        Estimated token count.
    """

    return sum(estimate_item_tokens(item) for item in items)


def estimate_history_tokens(history_items: list[dict[str, Any]]) -> int:
    """Compatibility alias for history token estimation.

    Args:
        history_items: History items.

    Returns:
        Estimated token count.
    """

    return estimate_items_tokens(history_items)
