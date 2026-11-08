"""Read-only catalog of meeting rooms."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class Room:
    """An immutable meeting room."""

    id: UUID
    name: str


class RoomRepository:
    """Store immutable rooms and provide lookup by identity."""

    def __init__(self, rooms: tuple[Room, ...]) -> None:
        """Build the fixed room catalog.

        Raises:
            ValueError: If room ids are duplicated.
        """
        self._rooms: dict[UUID, Room] = {}
        for room in rooms:
            if room.id in self._rooms:
                raise ValueError(f"Duplicate room id: '{room.id}'.")
            self._rooms[room.id] = room

    def get(self, room_id: UUID) -> Room | None:
        """Find a room by its identity."""
        return self._rooms.get(room_id)

    def list(self) -> list[Room]:
        """Return rooms in catalog order."""
        return list(self._rooms.values())


rooms = RoomRepository(
    (
        Room(id=UUID("824f2fde-0cfb-4354-83a8-181e7b372aa6"), name="Atlas"),
        Room(id=UUID("0dcf120a-73a6-4cad-871b-c325ce2f4beb"), name="Orion"),
        Room(id=UUID("a2213fc6-bbc0-49d2-95dc-50742a0bf735"), name="Vector"),
    )
)
