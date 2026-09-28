"""Unit tests for the contract models."""

from datetime import UTC, datetime, timedelta
from types import ModuleType
from typing import Any

import pytest
from pydantic import ValidationError

from app.constants import MIN_BOOKING_MINUTES, NOTES_MAX_LENGTH, PRICE_PER_HOUR, TITLE_MAX_LENGTH


class TestBookingCreateRequest:
    """Tests for the booking creation request model."""

    def test_accepts_valid_data(self, models: ModuleType, valid_create: dict[str, Any]) -> None:
        """A fully valid payload constructs successfully with every field intact."""
        booking = models.BookingCreateRequest(**valid_create)
        assert booking.title == valid_create["title"]
        assert booking.email == valid_create["email"]
        assert booking.phone == valid_create["phone"]
        assert booking.start_time == valid_create["start_time"]
        assert booking.end_time == valid_create["end_time"]
        assert booking.notes == valid_create["notes"]
        assert booking.internal_code == valid_create["internal_code"]

    @pytest.mark.parametrize(
        ["field", "value"],
        [
            pytest.param("title", "", id="title_empty"),
            pytest.param("title", "   ", id="title_whitespace_only"),
            pytest.param("title", "Bad <script>", id="title_reserved_chars"),
            pytest.param("email", "not-an-email", id="email_invalid_format"),
            pytest.param("phone", "5552671", id="phone_missing_plus"),
            pytest.param("phone", "+0123456", id="phone_leading_zero"),
            pytest.param("phone", "not-a-phone", id="phone_garbage"),
            pytest.param("phone", "+123456", id="phone_too_short"),
            pytest.param("phone", "+1234567890123456", id="phone_too_long"),
            pytest.param("notes", "hack; rm -rf $HOME", id="notes_reserved_chars"),
            pytest.param("title", "x" * (TITLE_MAX_LENGTH + 1), id="title_too_long"),
            pytest.param("notes", "x" * (NOTES_MAX_LENGTH + 1), id="notes_too_long"),
            pytest.param("start_time", "2099-01-01T10:00:00", id="start_time_naive"),
            pytest.param("end_time", "2099-01-01T11:00:00", id="end_time_naive"),
            pytest.param("surprise", "not allowed", id="extra_field_forbidden"),
        ],
    )
    def test_rejects_invalid_field(
        self, models: ModuleType, valid_create: dict[str, Any], field: str, value: str
    ) -> None:
        """Each case swaps one valid field for an invalid value and expects rejection."""
        kwargs = {**valid_create, field: value}
        with pytest.raises(ValidationError):
            models.BookingCreateRequest(**kwargs)

    @pytest.mark.parametrize("field", ["title", "email", "phone", "start_time", "end_time", "internal_code"])
    def test_requires_field(self, models: ModuleType, valid_create: dict[str, Any], field: str) -> None:
        """Each of these fields is mandatory; omitting it must fail."""
        kwargs = dict(valid_create)
        del kwargs[field]
        with pytest.raises(ValidationError):
            models.BookingCreateRequest(**kwargs)

    def test_notes_is_optional(self, models: ModuleType, valid_create: dict[str, Any]) -> None:
        """Omitting notes is fine and leaves every other field untouched."""
        kwargs = dict(valid_create)
        del kwargs["notes"]
        booking = models.BookingCreateRequest(**kwargs)
        assert booking.notes is None
        assert booking.title == valid_create["title"]
        assert booking.email == valid_create["email"]
        assert booking.phone == valid_create["phone"]
        assert booking.internal_code == valid_create["internal_code"]
        assert booking.start_time == valid_create["start_time"]
        assert booking.end_time == valid_create["end_time"]

    @pytest.mark.parametrize(
        ["start_offset", "end_offset"],
        [
            pytest.param(timedelta(days=-1), timedelta(hours=1), id="start_time_in_past"),
            pytest.param(timedelta(days=1), timedelta(minutes=MIN_BOOKING_MINUTES - 5), id="duration_too_short"),
            pytest.param(timedelta(days=1), timedelta(minutes=-30), id="end_before_start"),
        ],
    )
    def test_rejects_bad_time_window(
        self,
        models: ModuleType,
        valid_create: dict[str, Any],
        start_offset: timedelta,
        end_offset: timedelta,
    ) -> None:
        """A past start, a too-short gap, or an inverted window must all be rejected."""
        start = datetime.now(UTC) + start_offset
        end = start + end_offset
        kwargs = {**valid_create, "start_time": start, "end_time": end}
        with pytest.raises(ValidationError):
            models.BookingCreateRequest(**kwargs)

    def test_accepts_exact_minimum_duration(self, models: ModuleType, valid_create: dict[str, Any]) -> None:
        """A gap of exactly MIN_BOOKING_MINUTES is the accepted boundary, not rejected."""
        start = datetime.now(UTC) + timedelta(days=1)
        end = start + timedelta(minutes=MIN_BOOKING_MINUTES)
        kwargs = {**valid_create, "start_time": start, "end_time": end}
        booking = models.BookingCreateRequest(**kwargs)
        assert booking.start_time == start
        assert booking.end_time == end

    def test_trims_title(self, models: ModuleType, valid_create: dict[str, Any]) -> None:
        """Leading/trailing whitespace is stripped from the title."""
        kwargs = {**valid_create, "title": "  Test  "}
        booking = models.BookingCreateRequest(**kwargs)
        assert booking.title == "Test"

    def test_trims_notes(self, models: ModuleType, valid_create: dict[str, Any]) -> None:
        """Leading/trailing whitespace is stripped from notes."""
        kwargs = {**valid_create, "notes": "  test  "}
        booking = models.BookingCreateRequest(**kwargs)
        assert booking.notes == "test"

    @pytest.mark.parametrize("notes", ["", "   "], ids=["empty_string", "whitespace_only"])
    def test_empty_notes_becomes_none(self, models: ModuleType, valid_create: dict[str, Any], notes: str) -> None:
        """An empty or whitespace-only notes value is normalized to None, not rejected."""
        kwargs = {**valid_create, "notes": notes}
        booking = models.BookingCreateRequest(**kwargs)
        assert booking.notes is None

    def test_accepts_title_at_max_length(self, models: ModuleType, valid_create: dict[str, Any]) -> None:
        """A title of exactly TITLE_MAX_LENGTH characters is the accepted boundary."""
        kwargs = {**valid_create, "title": "x" * TITLE_MAX_LENGTH}
        booking = models.BookingCreateRequest(**kwargs)
        assert len(booking.title) == TITLE_MAX_LENGTH

    def test_accepts_notes_at_max_length(self, models: ModuleType, valid_create: dict[str, Any]) -> None:
        """Notes of exactly NOTES_MAX_LENGTH characters are the accepted boundary."""
        kwargs = {**valid_create, "notes": "x" * NOTES_MAX_LENGTH}
        booking = models.BookingCreateRequest(**kwargs)
        assert booking.notes is not None
        assert len(booking.notes) == NOTES_MAX_LENGTH


class TestBookingUpdateRequest:
    """Tests for the booking partial-update request model."""

    def test_accepts_valid_data(self, models: ModuleType, valid_update: dict[str, Any]) -> None:
        """A fully populated payload constructs successfully with every field intact."""
        update = models.BookingUpdateRequest(**valid_update)
        assert update.title == valid_update["title"]
        assert update.email == valid_update["email"]
        assert update.phone == valid_update["phone"]
        assert update.start_time == valid_update["start_time"]
        assert update.end_time == valid_update["end_time"]
        assert update.notes == valid_update["notes"]

    def test_all_fields_optional(self, models: ModuleType) -> None:
        """Every field defaults to None, so an empty payload is valid."""
        update = models.BookingUpdateRequest()
        assert update.title is None
        assert update.email is None
        assert update.phone is None
        assert update.start_time is None
        assert update.end_time is None
        assert update.notes is None

    @pytest.mark.parametrize(
        ["field", "value"],
        [
            pytest.param("title", "", id="title_empty"),
            pytest.param("title", "   ", id="title_whitespace_only"),
            pytest.param("title", "Bad <tag>", id="title_reserved_chars"),
            pytest.param("email", "not-an-email", id="email_invalid_format"),
            pytest.param("phone", "5552671", id="phone_missing_plus"),
            pytest.param("phone", "+0123456", id="phone_leading_zero"),
            pytest.param("phone", "not-a-phone", id="phone_garbage"),
            pytest.param("phone", "+123456", id="phone_too_short"),
            pytest.param("phone", "+1234567890123456", id="phone_too_long"),
            pytest.param("notes", "rm -rf $HOME", id="notes_reserved_chars"),
            pytest.param("title", "x" * (TITLE_MAX_LENGTH + 1), id="title_too_long"),
            pytest.param("notes", "x" * (NOTES_MAX_LENGTH + 1), id="notes_too_long"),
            pytest.param("start_time", "2099-01-01T10:00:00", id="start_time_naive"),
            pytest.param("end_time", "2099-01-01T11:00:00", id="end_time_naive"),
            pytest.param("surprise", "not allowed", id="extra_field_forbidden"),
        ],
    )
    def test_rejects_invalid_field(
        self, models: ModuleType, valid_update: dict[str, Any], field: str, value: str
    ) -> None:
        """Each case swaps one valid field for an invalid value and expects rejection."""
        kwargs = {**valid_update, field: value}
        with pytest.raises(ValidationError):
            models.BookingUpdateRequest(**kwargs)

    @pytest.mark.parametrize(
        ["start_offset", "end_offset"],
        [
            pytest.param(timedelta(days=-1), timedelta(hours=1), id="start_time_in_past"),
            pytest.param(timedelta(days=1), timedelta(minutes=MIN_BOOKING_MINUTES - 5), id="duration_too_short"),
            pytest.param(timedelta(days=1), timedelta(minutes=-30), id="end_before_start"),
        ],
    )
    def test_rejects_bad_time_window(
        self,
        models: ModuleType,
        valid_update: dict[str, Any],
        start_offset: timedelta,
        end_offset: timedelta,
    ) -> None:
        """A past start, a too-short gap, or an inverted window must be rejected when both times are given."""
        start = datetime.now(UTC) + start_offset
        end = start + end_offset
        kwargs = {**valid_update, "start_time": start, "end_time": end}
        with pytest.raises(ValidationError):
            models.BookingUpdateRequest(**kwargs)

    def test_accepts_exact_minimum_duration(self, models: ModuleType, valid_update: dict[str, Any]) -> None:
        """A gap of exactly MIN_BOOKING_MINUTES is the accepted boundary, not rejected."""
        start = datetime.now(UTC) + timedelta(days=1)
        end = start + timedelta(minutes=MIN_BOOKING_MINUTES)
        kwargs = {**valid_update, "start_time": start, "end_time": end}
        update = models.BookingUpdateRequest(**kwargs)
        assert update.start_time == start
        assert update.end_time == end

    @pytest.mark.parametrize(
        ["field", "other"],
        [
            pytest.param("start_time", "end_time", id="only_start_time"),
            pytest.param("end_time", "start_time", id="only_end_time"),
        ],
    )
    def test_single_time_field_skips_window_check(
        self, models: ModuleType, valid_update: dict[str, Any], field: str, other: str
    ) -> None:
        """Supplying just one of start/end time skips the cross-field window check."""
        update = models.BookingUpdateRequest(**{field: valid_update[field]})
        assert getattr(update, field) == valid_update[field]
        assert getattr(update, other) is None

    def test_trims_title(self, models: ModuleType, valid_update: dict[str, Any]) -> None:
        """Leading/trailing whitespace is stripped from the title."""
        kwargs = {**valid_update, "title": "  Test  "}
        update = models.BookingUpdateRequest(**kwargs)
        assert update.title == "Test"

    def test_trims_notes(self, models: ModuleType, valid_update: dict[str, Any]) -> None:
        """Leading/trailing whitespace is stripped from notes."""
        kwargs = {**valid_update, "notes": "  test  "}
        update = models.BookingUpdateRequest(**kwargs)
        assert update.notes == "test"

    @pytest.mark.parametrize("notes", ["", "   "], ids=["empty_string", "whitespace_only"])
    def test_empty_notes_becomes_none(self, models: ModuleType, valid_update: dict[str, Any], notes: str) -> None:
        """An empty or whitespace-only notes value is normalized to None, not rejected."""
        kwargs = {**valid_update, "notes": notes}
        update = models.BookingUpdateRequest(**kwargs)
        assert update.notes is None

    def test_accepts_title_at_max_length(self, models: ModuleType, valid_update: dict[str, Any]) -> None:
        """A title of exactly TITLE_MAX_LENGTH characters is the accepted boundary."""
        kwargs = {**valid_update, "title": "x" * TITLE_MAX_LENGTH}
        update = models.BookingUpdateRequest(**kwargs)
        assert update.title is not None
        assert len(update.title) == TITLE_MAX_LENGTH

    def test_accepts_notes_at_max_length(self, models: ModuleType, valid_update: dict[str, Any]) -> None:
        """Notes of exactly NOTES_MAX_LENGTH characters are the accepted boundary."""
        kwargs = {**valid_update, "notes": "x" * NOTES_MAX_LENGTH}
        update = models.BookingUpdateRequest(**kwargs)
        assert update.notes is not None
        assert len(update.notes) == NOTES_MAX_LENGTH


class TestBookingResponse:
    """Tests for the booking response model."""

    def test_accepts_valid_data(self, models: ModuleType, valid_response: dict[str, Any]) -> None:
        """A fully valid payload constructs successfully with every field intact."""
        response = models.BookingResponse(**valid_response)
        assert response.id == valid_response["id"]
        assert response.title == valid_response["title"]
        assert response.email == valid_response["email"]
        assert response.phone == valid_response["phone"]
        assert response.start_time == valid_response["start_time"]
        assert response.end_time == valid_response["end_time"]
        assert response.notes == valid_response["notes"]
        assert response.created_at == valid_response["created_at"]
        assert response.duration == 60
        assert response.price == round(PRICE_PER_HOUR, 2)

    def test_excludes_internal_code(self, models: ModuleType, valid_response: dict[str, Any]) -> None:
        """internal_code never appears in the dumped output, even if supplied."""
        kwargs = {**valid_response, "internal_code": "test-code"}
        response = models.BookingResponse(**kwargs)
        dumped = response.model_dump()
        assert dumped["id"] == "test-id"
        assert "internal_code" not in dumped

    def test_masks_phone_in_json(self, models: ModuleType, valid_response: dict[str, Any]) -> None:
        """The JSON-serialized phone keeps only its last four digits visible."""
        response = models.BookingResponse(**valid_response)
        assert response.model_dump(mode="json")["phone"] == "******6789"

    @pytest.mark.parametrize(
        ["hours", "expected_duration"],
        [
            pytest.param(0.25, 15, id="fifteen_minutes"),
            pytest.param(1, 60, id="one_hour"),
            pytest.param(2, 120, id="two_hours"),
        ],
    )
    def test_computes_duration_and_price(
        self,
        models: ModuleType,
        valid_response: dict[str, Any],
        hours: float,
        expected_duration: int,
    ) -> None:
        """Duration (minutes) and price (PRICE_PER_HOUR x hours) are derived from the time window."""
        start = valid_response["start_time"]
        kwargs = {**valid_response, "end_time": start + timedelta(hours=hours)}
        response = models.BookingResponse(**kwargs)
        assert response.duration == expected_duration
        assert response.price == round(hours * PRICE_PER_HOUR, 2)
