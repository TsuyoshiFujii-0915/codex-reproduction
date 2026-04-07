"""Approval helpers."""

from __future__ import annotations

from typing import Callable


class ApprovalRequiredError(RuntimeError):
    """Raised when an operation requires explicit approval."""


def ensure_approved(message: str, approval_handler: Callable[[str], bool] | None) -> None:
    """Require explicit approval for an operation."""
    if approval_handler is None:
        raise ApprovalRequiredError(message)
    approved: bool = approval_handler(message)
    if not approved:
        raise ApprovalRequiredError(message)
