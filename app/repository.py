"""Thread-safe, in-memory storage for bookings."""

import threading
import uuid
from datetime import UTC, datetime
from typing import Any


class BookingRepository:
    """An in-memory, thread-safe store of booking entities.

    Attributes:
        _items: Maps a booking id to its stored entity dictionary.
        _lock: Guards all reads and writes for thread safety.
    """

    def __init__(self) -> None:
        """Initialize an empty repository."""
        self._items: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def clear(self) -> None:
        """Remove every stored booking."""
        with self._lock:
            self._items.clear()

    def add(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Store a new booking entity and assign server-owned fields.

        Args:
            entity: The validated booking data.

        Returns:
            The stored entity.
        """
        booking_id = str(uuid.uuid4())
        record = {**entity, "id": booking_id, "created_at": datetime.now(UTC)}
        with self._lock:
            self._items[booking_id] = record
        return record

    def update(self, booking_id: str, changes: dict[str, Any]) -> dict[str, Any] | None:
        """Merge partial changes into a stored booking.

        Args:
            booking_id: The id of the booking to update.
            changes: Field values to merge in.

        Returns:
            The updated entity, or ``None`` if no booking has that id.
        """
        with self._lock:
            existing = self._items.get(booking_id)
            if existing is None:
                return None
            updated = {**existing, **changes}
            self._items[booking_id] = updated
            return updated

    def get(self, booking_id: str) -> dict[str, Any] | None:
        """Return one booking entity by id, or ``None`` if it is absent.

        Args:
            booking_id: The id to look up.

        Returns:
            The stored entity, or ``None``.
        """
        with self._lock:
            return self._items.get(booking_id)

    def list(
        self,
        *,
        limit: int,
        offset: int,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Return a filtered, paginated slice of bookings.

        Args:
            limit: Maximum number of results to return.
            offset: Number of leading results to skip.
            start_from: Keep bookings whose ``start_time`` is at or after this value.
            start_to: Keep bookings whose ``start_time`` is at or before this value.

        Returns:
            The matching entities for the requested page.
        """
        with self._lock:
            records = list(self._items.values())

        def _in_range(record: dict[str, Any]) -> bool:
            start = record["start_time"]
            if start_from is not None and start < start_from:
                return False
            if start_to is not None and start > start_to:
                return False
            return True

        filtered = [record for record in records if _in_range(record)]
        filtered.sort(key=lambda record: record["start_time"])
        return filtered[offset : offset + limit]


#: Module-level singleton used by the application and the tests.
repository = BookingRepository()
