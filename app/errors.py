"""Unified error envelope and exception handlers."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


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


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert a request-validation failure into the unified error envelope.

    Args:
        request: The incoming request.
        exc: The validation error FastAPI caught.

    Returns:
        A 422 response shaped like the envelope in README.md.
    """
    # TODO(12): Build details and return the envelope.
    raise NotImplementedError


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Convert an HTTPException into the unified error envelope.

    Args:
        request: The incoming request.
        exc: The HTTP exception FastAPI caught.

    Returns:
        A response with the same status code, shaped like the envelope in README.md.
    """
    # TODO(13): Return the envelope using information from exception.
    raise NotImplementedError
