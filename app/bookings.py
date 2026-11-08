"""Thread-safe, in-memory storage for bookings."""

from dataclasses import dataclass, field, fields, replace
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any
from uuid import UUID, uuid4

from .constants import MIN_BOOKING_MINUTES
from .exceptions import BookingConflictError, InvalidBookingWindowError


@dataclass(frozen=True, slots=True, kw_only=True)
class Booking:
    """An immutable stored booking.

    Fields marked with editable metadata may be changed through the repository.
    """

    id: UUID
    room_id: UUID
    title: str = field(metadata={"editable": True})
    email: str = field(metadata={"editable": True})
    phone: str = field(metadata={"editable": True})
    start_time: datetime = field(metadata={"editable": True})
    end_time: datetime = field(metadata={"editable": True})
    notes: str | None = field(metadata={"editable": True})
    created_at: datetime
    internal_code: str = field(repr=False)


class BookingRepository:
    """An in-memory, thread-safe store of booking entities.

    Attributes:
        _bookings: Maps a booking id to its stored Booking instance.
        _lock: Guards all reads and writes for thread safety.
    """

    def __init__(self, bookings: tuple[Booking, ...] = ()) -> None:
        """Initialize the repository with optional stored bookings.

        Args:
            bookings: Initial bookings; an empty tuple creates an empty repository.

        Raises:
            ValueError: If booking ids are duplicated.
            InvalidBookingWindowError: If a booking is shorter than the minimum duration.
            BookingConflictError: If initial bookings overlap in the same room.
        """
        self._bookings: dict[UUID, Booking] = {}
        self._lock = Lock()
        for booking in bookings:
            if booking.id in self._bookings:
                raise ValueError(f"Duplicate booking id: '{booking.id}'.")
            self._check_window(booking)
            self._check_overlap(booking)
            self._bookings[booking.id] = booking

    @staticmethod
    def _check_window(candidate: Booking) -> None:
        """Raise if the candidate ends less than the minimum duration after it starts.

        Args:
            candidate: The booking about to be stored.

        Raises:
            InvalidBookingWindowError: If the window is shorter than MIN_BOOKING_MINUTES.
        """
        if candidate.end_time - candidate.start_time < timedelta(minutes=MIN_BOOKING_MINUTES):
            raise InvalidBookingWindowError(
                f"Field 'end_time' must be at least {MIN_BOOKING_MINUTES} minutes after 'start_time'."
            )

    def _check_overlap(self, candidate: Booking) -> None:
        """Raise if the candidate's time window overlaps another booking in the same room.

        Args:
            candidate: The booking about to be stored.

        Raises:
            BookingConflictError: If another booking in the same room overlaps the candidate.
        """
        for other in self._bookings.values():
            if other.id == candidate.id or other.room_id != candidate.room_id:
                continue
            if candidate.start_time < other.end_time and other.start_time < candidate.end_time:
                raise BookingConflictError(f"Time window overlaps booking '{other.id}'.")

    def add(self, data: dict[str, Any]) -> Booking:
        """Store a new booking entity and assign server-owned fields.

        Args:
            data: The validated booking data.

        Returns:
            The stored entity.

        Raises:
            InvalidBookingWindowError: If the booking is shorter than the minimum duration.
            BookingConflictError: If the booking overlaps an existing one.
        """
        record = Booking(**{**data, "id": uuid4(), "created_at": datetime.now(UTC)})
        with self._lock:
            self._check_window(record)
            self._check_overlap(record)
            self._bookings[record.id] = record
        return record

    def update(self, booking_id: UUID, changes: dict[str, Any]) -> Booking | None:
        """Merge partial changes into a stored booking.

        Args:
            booking_id: The id of the booking to update.
            changes: Field values to merge in.

        Returns:
            The updated entity, or ``None`` if no booking has that id.

        Raises:
            ValueError: If changes include protected or unknown fields.
            InvalidBookingWindowError: If the updated booking is too short.
            BookingConflictError: If the updated booking overlaps another one.
        """
        editable_fields = {item.name for item in fields(Booking) if item.metadata.get("editable", False)}
        disallowed = changes.keys() - editable_fields
        if disallowed:
            raise ValueError(f"Cannot update protected booking fields: {', '.join(sorted(disallowed))}.")
        with self._lock:
            existing = self._bookings.get(booking_id)
            if existing is None:
                return None
            updated = replace(existing, **changes)
            self._check_window(updated)
            self._check_overlap(updated)
            self._bookings[booking_id] = updated
            return updated

    def get(self, booking_id: UUID) -> Booking | None:
        """Return one booking entity by id, or ``None`` if it is absent.

        Args:
            booking_id: The id to look up.

        Returns:
            The stored entity, or ``None``.
        """
        with self._lock:
            return self._bookings.get(booking_id)

    def list(
        self,
        *,
        limit: int,
        offset: int,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
        room_id: UUID | None = None,
    ) -> list[Booking]:
        """Return a filtered, paginated slice of bookings.

        Args:
            limit: Maximum number of results to return.
            offset: Number of leading results to skip.
            start_from: Keep bookings whose ``start_time`` is at or after this value.
            start_to: Keep bookings whose ``start_time`` is at or before this value.
            room_id: Restrict results to this room, if provided.

        Returns:
            The matching entities for the requested page.
        """
        with self._lock:
            records = list(self._bookings.values())
        filtered = [
            record
            for record in records
            if (room_id is None or record.room_id == room_id)
            and (start_from is None or record.start_time >= start_from)
            and (start_to is None or record.start_time <= start_to)
        ]
        filtered.sort(key=lambda record: (record.start_time, record.id))
        return filtered[offset : offset + limit]


bookings = BookingRepository()
