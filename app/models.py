"""Pydantic contract models for Roombook."""

import re

from pydantic import BaseModel, ConfigDict

# TODO(1): E.164 phone regex: leading "+", then 8-15 digits, first digit non-zero.
E164_PATTERN = re.compile(r"")

# TODO(2): Reserved characters to reject in free-text fields, e.g. <>{}$`;\
RESERVED_CHARS: set[str] = set()


class BookingBase(BaseModel):
    """Model for fields shared by every booking payload."""

    model_config = ConfigDict(extra="forbid")

    # TODO(3): Declare title, email, phone, start_time, end_time, notes (optional).
    # TODO(3): Needs `EmailStr`, `Field` from pydantic.

    # TODO(4): title validator -- trim; reject empty/whitespace-only; reject reserved chars; max length TITLE_MAX_LENGTH.
    # TODO(4): phone validator -- must match the E.164 pattern.
    # TODO(4): notes validator -- trim; reject reserved chars; empty becomes None; max length NOTES_MAX_LENGTH.
    # TODO(4): Needs `field_validator` from pydantic. Raise ValueError as "Field '<name>' <reason>."

    # TODO(5): model_validator(mode="after") -- reject a past start_time; require end_time >= start_time + MIN_BOOKING_MINUTES.
    # TODO(5): Needs `model_validator` from pydantic.


class BookingCreateRequest(BookingBase):
    """Model for creating a booking."""

    # TODO(6): Add the sensitive `internal_code` field. Needs `Field` from pydantic.


class BookingUpdateRequest(BaseModel):
    """Model for editing a booking."""

    model_config = ConfigDict(extra="forbid")

    # TODO(7): Optional versions of every editable field; reuse the validators.
    # TODO(7): Same length limits on title/notes as BookingBase.
    # TODO(7): Check the time window only when both times are present.


class BookingResponse(BaseModel):
    """Model for the booking response."""

    # TODO(8): Same fields as BookingBase, plus 'id' and 'created_at'.

    # TODO(9): 'field_serializer' for phone that masks all but the last four digits in JSON output. Needs `field_serializer` from pydantic.

    # TODO(10): Computed fields duration (in minutes) and price. Needs `computed_field` from pydantic.
