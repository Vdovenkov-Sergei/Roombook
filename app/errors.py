"""Unified error envelope and exception handlers."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException


class ErrorDetail(BaseModel):
    """One error associated with a request field."""

    model_config = ConfigDict(extra="forbid")

    field: str
    issue: str


class ErrorPayload(BaseModel):
    """Machine-readable error and its human-readable context."""

    model_config = ConfigDict(extra="forbid")

    type: str
    message: str
    details: list[ErrorDetail]


class ErrorResponse(BaseModel):
    """Standard response shape for all client errors."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorPayload


def build_error_body(error_type: str, message: str, details: list[dict[str, str]]) -> dict[str, Any]:
    """Assemble the standard error envelope.

    Args:
        error_type: A short machine-readable error code.
        message: A human-readable summary of what went wrong.
        details: Per-field problems, each shaped like {"field": ..., "issue": ...}.

    Returns:
        The envelope: {"error": {"type": ..., "message": ..., "details": ...}}.
    """
    # TODO(11): Build the envelope: error → type, message, details (field, issue).
    raise NotImplementedError


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Convert a request-validation failure into the unified error envelope.

    Args:
        request: The incoming request.
        exc: The validation error FastAPI caught.

    Returns:
        A 422 response shaped like the envelope in README.md.
    """
    # TODO(12): Return HTTP 422 with type "validation_error" and message
    #           "One or more fields are invalid.". Details: field (e.g. "body.title")
    #           and issue (validation message), without the original input values.
    raise NotImplementedError


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Convert an HTTPException into the unified error envelope.

    Args:
        request: The incoming request.
        exc: The HTTP exception FastAPI caught.

    Returns:
        A response with the same status code, shaped like the envelope in README.md.
    """
    # TODO(13): Return type "http_error", the exception detail as message and empty details.
    #           Preserve the exception's status code and headers.
    raise NotImplementedError
