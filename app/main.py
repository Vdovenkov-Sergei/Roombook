"""FastAPI application for Roombook."""

from datetime import datetime

from fastapi import FastAPI, Query

from .constants import DEFAULT_LIMIT, DEFAULT_OFFSET, MAX_LIMIT, MIN_LIMIT, MIN_OFFSET
from .models import BookingCreateRequest, BookingResponse, BookingUpdateRequest

app = FastAPI(
    title="Roombook",
    version="1.0.0",
    summary="A meeting-room booking API.",
)

# TODO(14): Register your exception handlers. Flag mypy errors with `# type: ignore` if needed.


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    """Report service liveness.

    Returns:
        A status document.
    """
    return {"status": "ok"}


@app.post("/api/bookings/", tags=["bookings"], response_model=BookingResponse)
def create_booking(payload: BookingCreateRequest) -> BookingResponse:
    """Create a booking.

    Args:
        payload: The validated booking request.

    Returns:
        The created booking.
    """
    # TODO(15): Store and return the created booking with the correct HTTP status code.
    raise NotImplementedError


@app.get("/api/bookings/{booking_id}", tags=["bookings"], response_model=BookingResponse)
def get_booking(booking_id: str) -> BookingResponse:
    """Retrieve a single booking by id.

    Args:
        booking_id: The id of the booking to retrieve.

    Returns:
        The matching booking.

    Raises:
        HTTPException: If no booking has the given id.
    """
    # TODO(16): Return the booking, or raise exception if it is absent.
    raise NotImplementedError


@app.patch("/api/bookings/{booking_id}", tags=["bookings"], response_model=BookingResponse)
def update_booking(booking_id: str, payload: BookingUpdateRequest) -> BookingResponse:
    """Apply a partial update to a booking.

    Args:
        booking_id: The id of the booking to update.
        payload: The fields to change.

    Returns:
        The updated booking.

    Raises:
        HTTPException: If no booking has the given id.
    """
    # TODO(17): Update the booking with only the fields the client actually set, or raise exception if it is absent.
    raise NotImplementedError


@app.get("/api/bookings/", tags=["bookings"], response_model=list[BookingResponse])
def list_bookings(
    limit: int = Query(default=DEFAULT_LIMIT, ge=MIN_LIMIT, le=MAX_LIMIT),
    offset: int = Query(default=DEFAULT_OFFSET, ge=MIN_OFFSET),
    start_from: datetime | None = Query(default=None),
    start_to: datetime | None = Query(default=None),
) -> list[BookingResponse]:
    """List bookings with pagination and an optional start-time range filter.

    Args:
        limit: Maximum number of bookings to return.
        offset: Number of leading bookings to skip.
        start_from: Keep bookings starting at or after this timestamp.
        start_to: Keep bookings starting at or before this timestamp.

    Returns:
        The matching page of bookings.
    """
    # TODO(18): Query the repository with the pagination and filter arguments.
    raise NotImplementedError
