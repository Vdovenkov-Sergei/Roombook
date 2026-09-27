"""Unified error envelope and exception handlers."""

from typing import Any

from fastapi import FastAPI


def build_error_body(error_type: str, message: str, details: list[dict[str, str]]) -> dict[str, Any]:
    """Assemble the standard error envelope.

    Args:
        error_type: A short machine-readable error code.
        message: A human-readable summary of what went wrong.
        details: Per-field problems, each shaped like {"field": ..., "issue": ...}.

    Returns:
        The envelope: {"error": {"type": ..., "message": ..., "details": ...}}.
    """
    # TODO(11): Return the envelope described in README.md.
    raise NotImplementedError


def register_exception_handlers(app: FastAPI) -> None:
    """Register the unified handlers on a FastAPI application.

    Args:
        app: The application to attach the handlers to.
    """
    # TODO(12): Register a RequestValidationError handler that returns 422 via `build_error_body`.
    # TODO(13): Register a StarletteHTTPException handler that returns the same envelope shape.
    raise NotImplementedError
