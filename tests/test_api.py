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

    def test_rejects_invalid_field(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """A changed field still goes through the same validation as on creation."""
        created = client.post("/api/bookings/", json=valid_create_json).json()
        response = client.patch(f"/api/bookings/{created['id']}", json={"phone": "not-a-phone"})
        assert response.status_code == 422

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
