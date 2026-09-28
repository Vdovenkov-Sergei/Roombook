"""End-to-end tests for the Roombook HTTP API."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.constants import MAX_LIMIT, MIN_LIMIT, PRICE_PER_HOUR, TITLE_MAX_LENGTH

# The exact set of fields a booking response must have.
BOOKING_RESPONSE_FIELDS = {
    "id",
    "title",
    "email",
    "phone",
    "start_time",
    "end_time",
    "notes",
    "created_at",
    "duration",
    "price",
}


def window(start: datetime, minutes: int) -> dict[str, str]:
    """Build the start/end time pair of a booking, as JSON strings.

    Args:
        start: When the booking starts.
        minutes: How long the booking lasts.

    Returns:
        A dict with ``start_time`` and ``end_time`` as ISO strings.
    """
    return {"start_time": start.isoformat(), "end_time": (start + timedelta(minutes=minutes)).isoformat()}


class TestHealth:
    """Tests for the liveness endpoint."""

    def test_returns_ok(self, client: TestClient) -> None:
        """GET /health reports the service is up."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCreateBooking:
    """Tests for POST /api/bookings/."""

    def test_creates_and_returns_full_booking(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """A valid payload is stored and echoed back with every field, masked and computed."""
        response = client.post("/api/bookings/", json=valid_create_json)
        assert response.status_code == 201
        body = response.json()
        assert set(body.keys()) == BOOKING_RESPONSE_FIELDS
        assert body["title"] == valid_create_json["title"]
        assert body["email"] == valid_create_json["email"]
        assert body["phone"] == "******6789"  # +123456789, masked
        assert body["notes"] == valid_create_json["notes"]
        assert body["id"]
        assert body["created_at"]
        assert body["duration"] == 60
        assert body["price"] == round(PRICE_PER_HOUR, 2)

    def test_never_leaks_internal_code(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """internal_code is required on the way in but must never appear on the way out."""
        response = client.post("/api/bookings/", json=valid_create_json)
        assert response.status_code == 201
        assert "internal_code" not in response.json()

    def test_trims_title_and_notes(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Leading/trailing whitespace is stripped before the booking is stored."""
        payload = {**valid_create_json, "title": "  Test  ", "notes": "  test  "}
        response = client.post("/api/bookings/", json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "Test"
        assert body["notes"] == "test"

    @pytest.mark.parametrize(
        ["overrides", "missing_field"],
        [
            pytest.param({"title": ""}, None, id="title_empty"),
            pytest.param({"phone": "not-a-phone"}, None, id="phone_garbage"),
            pytest.param({"notes": "hack; rm -rf $HOME"}, None, id="notes_reserved_chars"),
            pytest.param({"title": "x" * (TITLE_MAX_LENGTH + 1)}, None, id="title_too_long"),
            pytest.param({"start_time": "2099-01-01T10:00:00"}, None, id="start_time_naive"),
            pytest.param({}, "internal_code", id="internal_code_missing"),
            pytest.param({"surprise": "not allowed"}, None, id="extra_field_forbidden"),
        ],
    )
    def test_rejects_invalid_payload(
        self,
        client: TestClient,
        valid_create_json: dict[str, Any],
        overrides: dict[str, Any],
        missing_field: str | None,
    ) -> None:
        """One representative case per rule, the exact envelope shape is checked here too."""
        payload = {**valid_create_json, **overrides}
        if missing_field is not None:
            del payload[missing_field]
        response = client.post("/api/bookings/", json=payload)
        assert response.status_code == 422
        envelope = response.json()
        assert envelope["error"]["type"] == "validation_error"
        assert envelope["error"]["message"] == "One or more fields are invalid."
        assert envelope["error"]["details"]

    def test_rejects_end_before_start(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """The cross-field time-window rule surfaces through the API as a 422, not a 500."""
        start = datetime.now(UTC) + timedelta(days=1)
        end = start - timedelta(hours=1)
        payload = {**valid_create_json, "start_time": start.isoformat(), "end_time": end.isoformat()}
        response = client.post("/api/bookings/", json=payload)
        assert response.status_code == 422

    @pytest.mark.parametrize(
        ["offset_minutes", "duration_minutes"],
        [
            pytest.param(0, 60, id="identicalwindow"),
            pytest.param(30, 60, id="starts_inside_existing"),
            pytest.param(-30, 60, id="ends_inside_existing"),
            pytest.param(-15, 90, id="contains_existing"),
            pytest.param(15, 30, id="inside_existing"),
        ],
    )
    def test_rejects_overlapping_booking(
        self,
        client: TestClient,
        valid_create_json: dict[str, Any],
        offset_minutes: int,
        duration_minutes: int,
    ) -> None:
        """Any overlap with an existing booking is a 409 in the unified error envelope."""
        base = datetime.now(UTC) + timedelta(days=1)
        existing = {**valid_create_json, **window(base, 60)}
        assert client.post("/api/bookings/", json=existing).status_code == 201

        overlapping = {**valid_create_json, **window(base + timedelta(minutes=offset_minutes), duration_minutes)}
        response = client.post("/api/bookings/", json=overlapping)

        assert response.status_code == 409
        assert response.json()["error"]["type"] == "http_error"

    @pytest.mark.parametrize(
        "offset_minutes",
        [60, -30],
        ids=["starts_when_existing_ends", "ends_when_existing_starts"],
    )
    def test_allows_touching_bookings(
        self, client: TestClient, valid_create_json: dict[str, Any], offset_minutes: int
    ) -> None:
        """A booking that starts exactly when another ends is not an overlap."""
        base = datetime.now(UTC) + timedelta(days=1)
        existing = {**valid_create_json, **window(base, 60)}
        assert client.post("/api/bookings/", json=existing).status_code == 201

        touching = {**valid_create_json, **window(base + timedelta(minutes=offset_minutes), 30)}
        response = client.post("/api/bookings/", json=touching)

        assert response.status_code == 201

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
        client: TestClient,
        valid_create_json: dict[str, Any],
        hours: float,
        expected_duration: int,
    ) -> None:
        """Duration and price reflect the actual gap."""
        start = datetime.now(UTC) + timedelta(days=1)
        end = start + timedelta(hours=hours)
        payload = {**valid_create_json, "start_time": start.isoformat(), "end_time": end.isoformat()}
        response = client.post("/api/bookings/", json=payload)
        assert response.status_code == 201
        body = response.json()
        assert body["duration"] == expected_duration
        assert body["price"] == round(hours * PRICE_PER_HOUR, 2)


class TestGetBooking:
    """Tests for GET /api/bookings/{booking_id}."""

    def test_returns_existing_booking(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Fetching a booking returns exactly what creating it returned."""
        created = client.post("/api/bookings/", json=valid_create_json).json()
        response = client.get(f"/api/bookings/{created['id']}")
        assert response.status_code == 200
        assert response.json() == created

    def test_missing_booking_returns_404(self, client: TestClient) -> None:
        """An unknown id is a 404 in the unified error envelope, not an unhandled crash."""
        response = client.get("/api/bookings/does-not-exist")
        assert response.status_code == 404
        assert response.json()["error"]["type"] == "http_error"


class TestUpdateBooking:
    """Tests for PATCH /api/bookings/{booking_id}."""

    def test_changes_only_given_fields(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Every field except the one sent must be identical to the original."""
        created = client.post("/api/bookings/", json=valid_create_json).json()
        response = client.patch(f"/api/bookings/{created['id']}", json={"title": "Renamed"})
        assert response.status_code == 200
        assert response.json() == {**created, "title": "Renamed"}

    def test_missing_booking_returns_404(self, client: TestClient) -> None:
        """Updating an unknown id is a 404, not a 500."""
        response = client.patch("/api/bookings/does-not-exist", json={"title": "Renamed"})
        assert response.status_code == 404
        assert response.json()["error"]["type"] == "http_error"

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"title": ""}, id="title_empty"),
            pytest.param({"phone": "not-a-phone"}, id="phone_garbage"),
            pytest.param({"notes": "hack; rm -rf $HOME"}, id="notes_reserved_chars"),
            pytest.param({"title": "x" * (TITLE_MAX_LENGTH + 1)}, id="title_too_long"),
            pytest.param({"start_time": "2099-01-01T10:00:00"}, id="start_time_naive"),
            pytest.param({"surprise": "not allowed"}, id="extra_field_forbidden"),
        ],
    )
    def test_rejects_invalid_payload(
        self, client: TestClient, valid_create_json: dict[str, Any], overrides: dict[str, Any]
    ) -> None:
        """A changed field still goes through the same validation as on creation, envelope shape checked too."""
        created = client.post("/api/bookings/", json=valid_create_json).json()
        response = client.patch(f"/api/bookings/{created['id']}", json=overrides)
        assert response.status_code == 422
        envelope = response.json()
        assert envelope["error"]["type"] == "validation_error"
        assert envelope["error"]["message"] == "One or more fields are invalid."
        assert envelope["error"]["details"]

    def test_rejects_moving_into_a_conflict(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Moving a booking onto another booking's time is a 409."""
        base = datetime.now(UTC) + timedelta(days=1)
        first = {**valid_create_json, **window(base, 60)}
        assert client.post("/api/bookings/", json=first).status_code == 201
        second = client.post("/api/bookings/", json={**valid_create_json, **window(base + timedelta(hours=2), 60)})

        response = client.patch(
            f"/api/bookings/{second.json()['id']}",
            json=window(base + timedelta(minutes=30), 60),
        )

        assert response.status_code == 409
        assert response.json()["error"]["type"] == "http_error"

    def test_allows_shifting_within_ownwindow(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """A booking never conflicts with itself, so nudging its own time is fine."""
        base = datetime.now(UTC) + timedelta(days=1)
        created = client.post("/api/bookings/", json={**valid_create_json, **window(base, 60)}).json()

        response = client.patch(f"/api/bookings/{created['id']}", json=window(base + timedelta(minutes=10), 60))

        assert response.status_code == 200

    @pytest.mark.parametrize(
        ["field", "offset_minutes"],
        [
            pytest.param("end_time", -120, id="end_before_existing_start"),
            pytest.param("start_time", 120, id="start_after_existing_end"),
        ],
    )
    def test_rejects_change_that_leaveswindow_too_short(
        self, client: TestClient, valid_create_json: dict[str, Any], field: str, offset_minutes: int
    ) -> None:
        """Changing one end of the window alone must still leave a valid window, checked against the stored other end."""
        base = datetime.now(UTC) + timedelta(days=1)
        created = client.post("/api/bookings/", json={**valid_create_json, **window(base, 60)}).json()

        response = client.patch(
            f"/api/bookings/{created['id']}",
            json={field: (base + timedelta(minutes=offset_minutes)).isoformat()},
        )

        assert response.status_code == 422
        assert response.json()["error"]["type"] == "validation_error"

    def test_allows_extending_end_time_alone(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Moving just end time later is a valid partial update, and duration follows."""
        base = datetime.now(UTC) + timedelta(days=1)
        created = client.post("/api/bookings/", json={**valid_create_json, **window(base, 60)}).json()

        response = client.patch(
            f"/api/bookings/{created['id']}",
            json={"end_time": (base + timedelta(hours=2)).isoformat()},
        )

        assert response.status_code == 200
        assert response.json()["duration"] == 120

    def test_empty_body_changes_nothing(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """An empty PATCH body is valid and changes nothing."""
        created = client.post("/api/bookings/", json=valid_create_json).json()
        response = client.patch(f"/api/bookings/{created['id']}", json={})
        assert response.status_code == 200
        assert response.json() == created

    def test_changing_times_recomputes_duration_and_price(
        self, client: TestClient, valid_create_json: dict[str, Any]
    ) -> None:
        """Updating time fields recalculates the derived duration and price."""
        created = client.post("/api/bookings/", json=valid_create_json).json()
        start = datetime.now(UTC) + timedelta(days=1)
        end = start + timedelta(hours=2)
        response = client.patch(
            f"/api/bookings/{created['id']}",
            json={"start_time": start.isoformat(), "end_time": end.isoformat()},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["duration"] == 120
        assert body["price"] == round(2 * PRICE_PER_HOUR, 2)


class TestListBookings:
    """Tests for GET /api/bookings/."""

    def test_empty_by_default(self, client: TestClient) -> None:
        """No bookings means an empty list, not an error."""
        response = client.get("/api/bookings/")
        assert response.status_code == 200
        assert response.json() == []

    def test_pagination(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Limit/offset slice the results, ordered by time."""
        base = datetime.now(UTC) + timedelta(days=2)
        for index in range(5):
            start = base + timedelta(hours=index)
            end = start + timedelta(minutes=30)
            payload = {
                **valid_create_json,
                "title": f"Booking {index}",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }
            assert client.post("/api/bookings/", json=payload).status_code == 201

        page = client.get("/api/bookings/", params={"limit": 2, "offset": 0})
        assert page.status_code == 200
        assert [item["title"] for item in page.json()] == ["Booking 0", "Booking 1"]

        last_page = client.get("/api/bookings/", params={"limit": 2, "offset": 4})
        assert [item["title"] for item in last_page.json()] == ["Booking 4"]

    def test_date_range_filter_is_inclusive(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Filter by time range include bookings starting exactly at either boundary."""
        base = datetime.now(UTC) + timedelta(days=3)
        starts = [base + timedelta(hours=index) for index in range(3)]
        for index, start in enumerate(starts):
            end = start + timedelta(minutes=30)
            payload = {
                **valid_create_json,
                "title": f"Range {index}",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }
            client.post("/api/bookings/", json=payload)

        response = client.get(
            "/api/bookings/",
            params={"start_from": starts[1].isoformat(), "start_to": starts[1].isoformat()},
        )
        assert response.status_code == 200
        titles = [item["title"] for item in response.json()]
        assert titles == ["Range 1"]

    def test_date_range_filter_start_from_only(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Time start alone keeps every booking from that point onward."""
        base = datetime.now(UTC) + timedelta(days=4)
        starts = [base + timedelta(hours=index) for index in range(3)]
        for index, start in enumerate(starts):
            end = start + timedelta(minutes=30)
            payload = {
                **valid_create_json,
                "title": f"From {index}",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }
            client.post("/api/bookings/", json=payload)

        response = client.get("/api/bookings/", params={"start_from": starts[1].isoformat()})
        assert response.status_code == 200
        titles = [item["title"] for item in response.json()]
        assert titles == ["From 1", "From 2"]

    def test_date_range_filter_start_to_only(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Time end alone keeps every booking up to that point."""
        base = datetime.now(UTC) + timedelta(days=5)
        starts = [base + timedelta(hours=index) for index in range(3)]
        for index, start in enumerate(starts):
            end = start + timedelta(minutes=30)
            payload = {
                **valid_create_json,
                "title": f"To {index}",
                "start_time": start.isoformat(),
                "end_time": end.isoformat(),
            }
            client.post("/api/bookings/", json=payload)

        response = client.get("/api/bookings/", params={"start_to": starts[1].isoformat()})
        assert response.status_code == 200
        titles = [item["title"] for item in response.json()]
        assert titles == ["To 0", "To 1"]

    @pytest.mark.parametrize("limit", [MIN_LIMIT - 1, MAX_LIMIT + 1], ids=["limit_too_low", "limit_too_high"])
    def test_limit_out_of_range_rejected(self, client: TestClient, limit: int) -> None:
        """Limit is bounded by MIN_LIMIT/MAX_LIMIT."""
        response = client.get("/api/bookings/", params={"limit": limit})
        assert response.status_code == 422

    def test_negative_offset_rejected(self, client: TestClient) -> None:
        """Offset can't be negative."""
        response = client.get("/api/bookings/", params={"offset": -1})
        assert response.status_code == 422

    @pytest.mark.parametrize("param", ["start_from", "start_to"])
    def test_naive_range_filter_rejected(self, client: TestClient, param: str) -> None:
        """A range filter without a timezone is a 422, not a crash."""
        response = client.get("/api/bookings/", params={param: "2099-01-01T10:00:00"})
        assert response.status_code == 422
