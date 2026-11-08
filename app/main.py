"""FastAPI application for Roombook."""

from typing import Any
from uuid import UUID

from fastapi import FastAPI, Query, status
from pydantic import AwareDatetime

from .bookings import bookings as bookings
from .constants import DEFAULT_LIMIT, DEFAULT_OFFSET, MAX_LIMIT, MIN_LIMIT, MIN_OFFSET
from .errors import ErrorResponse
from .models import (
    BookingCreateRequest,
    BookingResponse,
    BookingUpdateRequest,
)
from .rooms import Room, rooms

CLIENT_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Resource not found"},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Booking time conflict"},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": ErrorResponse, "description": "Invalid request or booking window"},
}

app = FastAPI(title="Roombook", version="1.0.0", summary="A meeting-room booking API.")


# TODO(14): Register your exception handlers.


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Report service liveness.

    Returns:
        A status document.
    """
    return {"status": "ok"}


@app.get("/api/rooms/", tags=["rooms"], response_model=list[Room])
def get_rooms() -> list[Room]:
    """List the rooms available for booking."""
    return rooms.list()


@app.get(
    "/api/rooms/{room_id}",
    tags=["rooms"],
    response_model=Room,
    responses={
        status.HTTP_404_NOT_FOUND: CLIENT_ERRORS[status.HTTP_404_NOT_FOUND],
        status.HTTP_422_UNPROCESSABLE_ENTITY: CLIENT_ERRORS[status.HTTP_422_UNPROCESSABLE_ENTITY],
    },
)
def get_room_by_id(room_id: UUID) -> Room:
    """Retrieve one room."""
    # TODO(15): Return the room, or raise '404 Not Found' if it is absent.
    raise NotImplementedError


@app.post(
    "/api/bookings/",
    tags=["bookings"],
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    responses=CLIENT_ERRORS,
)
def create_booking(payload: BookingCreateRequest) -> BookingResponse:
    """Create a booking.

    Args:
        payload: The validated booking request.

    Returns:
        The created booking.

    Raises:
        HTTPException: If the room is absent, or the booking's time overlaps an existing booking in that room.
    """
    # TODO(16): Store and return the created booking with the correct HTTP status code.
    # TODO(16): An unknown room must become '404 Not Found'.
    # TODO(16): A time conflict reported by the repository must become '409 Conflict'.
    raise NotImplementedError


@app.get(
    "/api/bookings/{booking_id}",
    tags=["bookings"],
    response_model=BookingResponse,
    responses={
        status.HTTP_404_NOT_FOUND: CLIENT_ERRORS[status.HTTP_404_NOT_FOUND],
        status.HTTP_422_UNPROCESSABLE_ENTITY: CLIENT_ERRORS[status.HTTP_422_UNPROCESSABLE_ENTITY],
    },
)
def get_booking(booking_id: UUID) -> BookingResponse:
    """Retrieve a single booking by id.

    Args:
        booking_id: The id of the booking to retrieve.

    Returns:
        The matching booking.

    Raises:
        HTTPException: If no booking has the given id.
    """
    # TODO(17): Return the booking, or raise exception '404 Not Found' if it is absent.
    raise NotImplementedError


@app.patch(
    "/api/bookings/{booking_id}",
    tags=["bookings"],
    response_model=BookingResponse,
    responses=CLIENT_ERRORS,
)
def update_booking(booking_id: UUID, payload: BookingUpdateRequest) -> BookingResponse:
    """Apply a partial update to a booking.

    Args:
        booking_id: The id of the booking to update.
        payload: The fields to change.

    Returns:
        The updated booking.

    Raises:
        HTTPException: If no booking has the given id, the new time overlaps another booking
            in the same room, or the new window is shorter than the minimum duration.
    """
    # TODO(18): Update the booking with only the fields the client actually set, or raise '404 Not Found' if it is absent.
    # TODO(18): A time conflict reported by the repository must become '409 Conflict'.
    # TODO(18): A too-short window reported by the repository must become HTTP 422 in the unified error envelope.
    raise NotImplementedError


@app.get(
    "/api/bookings/",
    tags=["bookings"],
    response_model=list[BookingResponse],
    responses={
        status.HTTP_404_NOT_FOUND: CLIENT_ERRORS[status.HTTP_404_NOT_FOUND],
        status.HTTP_422_UNPROCESSABLE_ENTITY: CLIENT_ERRORS[status.HTTP_422_UNPROCESSABLE_ENTITY],
    },
)
def list_bookings(
    limit: int = Query(default=DEFAULT_LIMIT, ge=MIN_LIMIT, le=MAX_LIMIT),
    offset: int = Query(default=DEFAULT_OFFSET, ge=MIN_OFFSET),
    start_from: AwareDatetime | None = Query(default=None),
    start_to: AwareDatetime | None = Query(default=None),
    room_id: UUID | None = Query(default=None),
) -> list[BookingResponse]:
    """List bookings with pagination and optional room and start-time range filters.

    Args:
        limit: Maximum number of bookings to return.
        offset: Number of leading bookings to skip.
        start_from: Keep bookings starting at or after this timestamp.
        start_to: Keep bookings starting at or before this timestamp.
        room_id: Restrict results to this room, if provided.

    Returns:
        The matching page of bookings.

    Raises:
        HTTPException: If the room is absent or the start-time range is reversed.
    """
    # TODO(19): Query the repository with the pagination and filter arguments.
    # TODO(19): An unknown room must become '404 Not Found'; a reversed time range must become HTTP 422.
    raise NotImplementedError
