"""Pydantic contract models for Roombook."""

import re

from pydantic import BaseModel, ConfigDict

# TODO(1): E.164 phone regex: leading "+", then 8-15 ASCII digits, first digit non-zero.
E164_PATTERN = re.compile(r"")


class BookingBase(BaseModel):
    """Fields shared by booking creation and representation."""

    model_config = ConfigDict(extra="forbid")

    # TODO(2): Declare `room_id`, `title`, `email`, `phone`, `start_time`, `end_time`, `notes`.
    #          Use `UUID`, `EmailStr` and `AwareDatetime`; only notes may be omitted.

    # TODO(3): Validate/trim `title`; reject blanks and lengths > TITLE_MAX_LENGTH.
    #          Validate `phone` using E164_PATTERN.
    #          Trim `notes`, normalize empty to None, enforce NOTES_MAX_LENGTH.
    #          Ordinary free-text punctuation is allowed.
    #          Reuse this behavior in `BookingUpdateRequest` without duplication.


class BookingCreateRequest(BookingBase):
    """Client payload for creating a booking."""

    # TODO(4): Add mandatory `internal_code` with at least one character.
    #          Exclude it from repr and all public API responses.

    # TODO(5): At model level, require future `start_time` and minimum duration.
    #          The minimum duration is MIN_BOOKING_MINUTES.


class BookingUpdateRequest(BaseModel):
    """Client payload for a partial booking update."""

    model_config = ConfigDict(extra="forbid")

    # TODO(6): Declare `title`, `email`, `phone`, `start_time`, `end_time`, `notes`.
    #          Every field may be omitted; `room_id` and `internal_code` cannot be changed.
    #          Explicit null must be rejected for `title`, `email`, `phone`,
    #          `start_time` and `end_time`; `notes` = null is valid.

    # TODO(7): Reuse `title`, `phone` and `notes` validators from creation.
    #          If `start_time` is supplied, require it to be in the future.
    #          Check minimum duration only if both boundaries are supplied.
    #          A single-boundary update is checked after merging in repository.


class BookingResponse(BookingBase):
    """Public representation of a stored booking."""

    # TODO(8): Add `id: UUID` and timezone-aware `created_at`.
    #          Keep extra 'forbid'; do not pass private fields to the response model.

    # TODO(9): Mask phone in JSON only; replace every character except the last four with *.

    # TODO(10): Provide computed `duration` (whole minutes) and numeric `price`.
    #           Price uses PRICE_PER_HOUR and the full interval, including microseconds.
    #           Round to two decimal places, rounding exact halves up.
