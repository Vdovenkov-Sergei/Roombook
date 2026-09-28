"""Shared pytest fixtures for the Roombook tests."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic_core import to_jsonable_python

from app import main as _main
from app import models as _models
from app.repository import BookingRepository
from app.repository import repository as _repository


@pytest.fixture()
def models() -> ModuleType:
    """Give a test the ``app.models`` module, so it can build models directly.

    Returns:
        The ``app.models`` module.
    """
    return _models


@pytest.fixture()
def repository() -> BookingRepository:
    """Give a test the app's repository, reset to empty first.

    Returns:
        The shared ``BookingRepository`` instance, freshly cleared.
    """
    _repository.clear()
    return _repository


@pytest.fixture()
def client(repository: BookingRepository) -> Iterator[TestClient]:
    """Give a test an HTTP client wired to the app, with an empty repository.

    Args:
        repository: The cleared repository.

    Yields:
        A ``TestClient`` bound to the FastAPI app, open for the test's duration.
    """
    with TestClient(_main.app) as test_client:
        yield test_client


def as_json_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Reshape Python constructor kwargs into a JSON-safe request body.

    Args:
        data: Constructor kwargs built with native Python types.

    Returns:
        The same data, shaped like a real client's JSON request body.
    """
    payload: dict[str, Any] = to_jsonable_python(data)
    return payload


@pytest.fixture()
def valid_create() -> dict[str, Any]:
    """A correct, complete set of ``BookingCreateRequest`` constructor kwargs."""
    start = datetime.now(UTC) + timedelta(days=1)
    return {
        "title": "Test",
        "email": "test@example.com",
        "phone": "+123456789",
        "start_time": start,
        "end_time": start + timedelta(hours=1),
        "notes": "test",
        "internal_code": "test-code",
    }


@pytest.fixture()
def valid_create_json(valid_create: dict[str, Any]) -> dict[str, Any]:
    """A JSON correct, complete set of ``BookingCreateRequest`` constructor kwargs."""
    return as_json_payload(valid_create)


@pytest.fixture()
def valid_update() -> dict[str, Any]:
    """A correct, fully populated set of ``BookingUpdateRequest`` constructor kwargs."""
    start = datetime.now(UTC) + timedelta(days=1)
    return {
        "title": "Test",
        "email": "test@example.com",
        "phone": "+123456789",
        "start_time": start,
        "end_time": start + timedelta(hours=1),
        "notes": "test",
    }


@pytest.fixture()
def valid_response() -> dict[str, Any]:
    """A correct, complete set of ``BookingResponse`` constructor kwargs."""
    start = datetime.now(UTC)
    return {
        "id": "test-id",
        "title": "Test",
        "email": "test@example.com",
        "phone": "+123456789",
        "start_time": start,
        "end_time": start + timedelta(hours=1),
        "notes": "test",
        "created_at": start,
    }
