"""End-to-end tests for the Roombook HTTP API."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.bookings import BookingRepository
from app.constants import MAX_LIMIT, MIN_LIMIT, PRICE_PER_HOUR, TITLE_MAX_LENGTH

# The exact set of fields a booking response must have.
BOOKING_RESPONSE_FIELDS = {
    "id",
    "room_id",
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


def create_booking(client: TestClient, payload: dict[str, Any]) -> dict[str, Any]:
    """Create a test booking and require a successful response.

    Args:
        client: Test application client.
        payload: The booking request.

    Returns:
        The new booking response body.
    """
    response = client.post("/api/bookings/", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def assert_error(response: Any, *, status: int, error_type: str) -> dict[str, Any]:
    """Verify the complete unified error envelope.

    Args:
        response: HTTP response to inspect.
        status: Expected HTTP status.
        error_type: Expected machine-readable error type.

    Returns:
        The validated error payload.
    """
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"type", "message", "details"}
    assert body["error"]["type"] == error_type
    assert isinstance(body["error"]["message"], str) and body["error"]["message"]
    assert isinstance(body["error"]["details"], list)
    assert all(set(item) == {"field", "issue"} for item in body["error"]["details"])
    assert all(
        isinstance(item["field"], str) and item["field"] and isinstance(item["issue"], str) and item["issue"]
        for item in body["error"]["details"]
    )
    return body["error"]


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
        assert body["room_id"] == valid_create_json["room_id"]
        assert body["title"] == valid_create_json["title"]
        assert body["email"] == valid_create_json["email"]
        assert body["phone"] == "******6789"  # +123456789, masked
        assert body["notes"] == valid_create_json["notes"]
        assert UUID(body["id"]).version == 4
        assert datetime.fromisoformat(body["created_at"]).tzinfo is not None
        assert datetime.fromisoformat(body["start_time"]) == datetime.fromisoformat(valid_create_json["start_time"])
        assert datetime.fromisoformat(body["end_time"]) == datetime.fromisoformat(valid_create_json["end_time"])
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
        assert_error(response, status=422, error_type="validation_error")

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

    def test_persists_internal_code_privately(
        self,
        client: TestClient,
        repository: BookingRepository,
        valid_create_json: dict[str, Any],
    ) -> None:
        """The repository retains private data without sending it to clients."""
        created = create_booking(client, valid_create_json)
        record = repository.get(UUID(created["id"]))
        assert record is not None
        assert record.internal_code == valid_create_json["internal_code"]
        assert "internal_code" not in created

    @pytest.mark.parametrize("field", ["room_id", "title", "internal_code", "start_time"])
    def test_rejects_missing_required_field(
        self, client: TestClient, valid_create_json: dict[str, Any], field: str
    ) -> None:
        """Required fields must appear in requests."""
        payload = {key: value for key, value in valid_create_json.items() if key != field}
        error = assert_error(
            client.post("/api/bookings/", json=payload),
            status=422,
            error_type="validation_error",
        )
        assert any(item["field"] == f"body.{field}" for item in error["details"])

    def test_unknown_room_returns_404(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """A syntactically valid but nonexistent room is a missing resource."""
        response = client.post(
            "/api/bookings/", json={**valid_create_json, "room_id": "ffffffff-ffff-4fff-8fff-ffffffffffff"}
        )
        assert_error(response, status=404, error_type="http_error")

    def test_rejects_too_short_interval(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Cross-field window errors are surfaced as 422, not 500."""
        start = datetime.now(UTC) + timedelta(days=1)
        response = client.post("/api/bookings/", json={**valid_create_json, **window(start, 10)})
        assert_error(response, status=422, error_type="validation_error")

    def test_allows_same_time_in_different_rooms(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Only bookings for the same room are mutually exclusive."""
        created = create_booking(client, valid_create_json)
        other = create_booking(client, {**valid_create_json, "room_id": "0dcf120a-73a6-4cad-871b-c325ce2f4beb"})
        assert created["id"] != other["id"]
        assert created["start_time"] == other["start_time"]

    def test_timezone_offsets_represent_same_instant(
        self, client: TestClient, valid_create_json: dict[str, Any]
    ) -> None:
        """Equivalent times in different offsets must conflict."""
        base = datetime(2099, 4, 1, 10, tzinfo=UTC)
        create_booking(client, {**valid_create_json, **window(base, 60)})
        response = client.post(
            "/api/bookings/",
            json={
                **valid_create_json,
                "start_time": "2099-04-01T12:15:00+02:00",
                "end_time": "2099-04-01T12:45:00+02:00",
            },
        )
        assert_error(response, status=409, error_type="http_error")


class TestGetBooking:
    """Tests for GET /api/bookings/{booking_id}."""

    def test_returns_existing_booking(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Fetching a booking returns exactly what creating it returned."""
        created = create_booking(client, valid_create_json)
        response = client.get(f"/api/bookings/{created['id']}")
        assert response.status_code == 200
        assert response.json() == created

    def test_missing_booking_returns_404(self, client: TestClient) -> None:
        """An unknown id is a 404 in the unified error envelope, not an unhandled crash."""
        response = client.get("/api/bookings/ffffffff-ffff-4fff-8fff-ffffffffffff")
        assert response.status_code == 404
        assert response.json()["error"]["type"] == "http_error"

    def test_can_retrieve_historical_booking(
        self,
        client: TestClient,
        repository: BookingRepository,
        valid_create: dict[str, Any],
    ) -> None:
        """Reading a historical booking does not rerun create-only date checks."""
        start = datetime.now(UTC) - timedelta(days=10)
        stored = repository.add(
            {
                **valid_create,
                "start_time": start,
                "end_time": start + timedelta(hours=1),
            }
        )
        response = client.get(f"/api/bookings/{stored.id}")
        assert response.status_code == 200
        assert response.json()["duration"] == 60


class TestUpdateBooking:
    """Tests for PATCH /api/bookings/{booking_id}."""

    def test_changes_only_given_fields(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Every field except the one sent must be identical to the original."""
        created = create_booking(client, valid_create_json)
        response = client.patch(f"/api/bookings/{created['id']}", json={"title": "Renamed"})
        assert response.status_code == 200
        assert response.json() == {**created, "title": "Renamed"}

    def test_missing_booking_returns_404(self, client: TestClient) -> None:
        """Updating an unknown id is a 404, not a 500."""
        response = client.patch("/api/bookings/ffffffff-ffff-4fff-8fff-ffffffffffff", json={"title": "Renamed"})
        assert response.status_code == 404
        assert response.json()["error"]["type"] == "http_error"

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"title": ""}, id="title_empty"),
            pytest.param({"phone": "not-a-phone"}, id="phone_garbage"),
            pytest.param({"title": "x" * (TITLE_MAX_LENGTH + 1)}, id="title_too_long"),
            pytest.param({"start_time": "2099-01-01T10:00:00"}, id="start_time_naive"),
            pytest.param({"surprise": "not allowed"}, id="extra_field_forbidden"),
        ],
    )
    def test_rejects_invalid_payload(
        self, client: TestClient, valid_create_json: dict[str, Any], overrides: dict[str, Any]
    ) -> None:
        """A changed field still goes through the same validation as on creation, envelope shape checked too."""
        created = create_booking(client, valid_create_json)
        response = client.patch(f"/api/bookings/{created['id']}", json=overrides)
        assert response.status_code == 422
        envelope = response.json()
        assert envelope["error"]["type"] == "validation_error"
        assert envelope["error"]["message"] == "One or more fields are invalid."
        assert envelope["error"]["details"]
        assert_error(response, status=422, error_type="validation_error")

    def test_rejects_moving_into_a_conflict(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Moving a booking onto another booking's time is a 409."""
        base = datetime.now(UTC) + timedelta(days=1)
        first = {**valid_create_json, **window(base, 60)}
        assert client.post("/api/bookings/", json=first).status_code == 201
        second = client.post("/api/bookings/", json={**valid_create_json, **window(base + timedelta(hours=2), 60)})
        assert second.status_code == 201

        response = client.patch(
            f"/api/bookings/{second.json()['id']}",
            json=window(base + timedelta(minutes=30), 60),
        )

        assert response.status_code == 409
        assert response.json()["error"]["type"] == "http_error"

    def test_allows_shifting_within_ownwindow(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """A booking never conflicts with itself, so nudging its own time is fine."""
        base = datetime.now(UTC) + timedelta(days=1)
        created = create_booking(client, {**valid_create_json, **window(base, 60)})

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
        created = create_booking(client, {**valid_create_json, **window(base, 60)})

        response = client.patch(
            f"/api/bookings/{created['id']}",
            json={field: (base + timedelta(minutes=offset_minutes)).isoformat()},
        )

        assert response.status_code == 422
        assert_error(response, status=422, error_type="http_error")
        assert client.get(f"/api/bookings/{created['id']}").json() == created

    def test_allows_extending_end_time_alone(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Moving just end time later is a valid partial update, and duration follows."""
        base = datetime.now(UTC) + timedelta(days=1)
        created = create_booking(client, {**valid_create_json, **window(base, 60)})

        response = client.patch(
            f"/api/bookings/{created['id']}",
            json={"end_time": (base + timedelta(hours=2)).isoformat()},
        )

        assert response.status_code == 200
        assert response.json()["duration"] == 120

    def test_empty_body_changes_nothing(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """An empty PATCH body is valid and changes nothing."""
        created = create_booking(client, valid_create_json)
        response = client.patch(f"/api/bookings/{created['id']}", json={})
        assert response.status_code == 200
        assert response.json() == created

    def test_changing_times_recomputes_duration_and_price(
        self, client: TestClient, valid_create_json: dict[str, Any]
    ) -> None:
        """Updating time fields recalculates the derived duration and price."""
        created = create_booking(client, valid_create_json)
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

    def test_clears_notes_with_null(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Notes may be explicitly cleared, unlike mandatory fields."""
        original = create_booking(client, valid_create_json)
        response = client.patch(f"/api/bookings/{original['id']}", json={"notes": None})
        assert response.status_code == 200
        assert response.json()["notes"] is None

    @pytest.mark.parametrize("field", ["title", "email", "phone", "start_time", "end_time"])
    def test_rejects_null_for_required_field(
        self, client: TestClient, valid_create_json: dict[str, Any], field: str
    ) -> None:
        """An explicit null cannot corrupt a required field."""
        created = create_booking(client, valid_create_json)
        error = assert_error(
            client.patch(f"/api/bookings/{created['id']}", json={field: None}),
            status=422,
            error_type="validation_error",
        )
        assert error["details"]
        assert client.get(f"/api/bookings/{created['id']}").json() == created

    @pytest.mark.parametrize("field", ["room_id", "internal_code", "created_at", "id"])
    def test_rejects_protected_field(self, client: TestClient, valid_create_json: dict[str, Any], field: str) -> None:
        """The PATCH contract does not allow resource identity changes."""
        created = create_booking(client, valid_create_json)
        assert_error(
            client.patch(f"/api/bookings/{created['id']}", json={field: "malicious"}),
            status=422,
            error_type="validation_error",
        )

    def test_rejects_conflicting_update_without_modifying_record(
        self, client: TestClient, valid_create_json: dict[str, Any]
    ) -> None:
        """A failed conflict check cannot partially persist a change."""
        base = datetime.now(UTC) + timedelta(days=5)
        create_booking(client, {**valid_create_json, **window(base, 60)})
        original = create_booking(client, {**valid_create_json, **window(base + timedelta(hours=2), 60)})
        response = client.patch(
            f"/api/bookings/{original['id']}",
            json=window(base + timedelta(minutes=30), 60),
        )
        assert_error(response, status=409, error_type="http_error")
        assert client.get(f"/api/bookings/{original['id']}").json() == original


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
            assert client.post("/api/bookings/", json=payload).status_code == 201

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
            assert client.post("/api/bookings/", json=payload).status_code == 201

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
            assert client.post("/api/bookings/", json=payload).status_code == 201

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

    def test_filters_by_room(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """Room filtering excludes bookings of all other rooms."""
        create_booking(client, valid_create_json)
        create_booking(client, {**valid_create_json, "room_id": "0dcf120a-73a6-4cad-871b-c325ce2f4beb"})
        response = client.get("/api/bookings/", params={"room_id": "0dcf120a-73a6-4cad-871b-c325ce2f4beb"})
        assert response.status_code == 200
        (booking,) = response.json()
        assert booking["room_id"] == "0dcf120a-73a6-4cad-871b-c325ce2f4beb"
        assert "internal_code" not in booking

    def test_combines_filters_before_sorted_pagination(
        self, client: TestClient, valid_create_json: dict[str, Any]
    ) -> None:
        """Room and inclusive time filters apply before chronological sorting and pagination."""
        base = datetime.now(UTC) + timedelta(days=3)
        start_from = base + timedelta(hours=1)
        start_to = base + timedelta(hours=3)
        room_id = valid_create_json["room_id"]
        other_room_id = "0dcf120a-73a6-4cad-871b-c325ce2f4beb"
        expected_booking = create_booking(client, {**valid_create_json, **window(start_to, 30)})
        for start, booking_room_id in (
            (start_to + timedelta(hours=1), room_id),
            (start_from, other_room_id),
            (start_from + timedelta(hours=1), room_id),
            (base, room_id),
        ):
            create_booking(client, {**valid_create_json, "room_id": booking_room_id, **window(start, 30)})
        response = client.get(
            "/api/bookings/",
            params={
                "room_id": valid_create_json["room_id"],
                "start_from": start_from.isoformat(),
                "start_to": start_to.isoformat(),
                "limit": 1,
                "offset": 1,
            },
        )
        assert response.status_code == 200
        assert response.json() == [expected_booking]

    def test_list_preserves_public_response_contract(
        self, client: TestClient, valid_create_json: dict[str, Any]
    ) -> None:
        """Listing uses the same public fields, phone mask and computed values as creation."""
        created = create_booking(client, valid_create_json)
        response = client.get("/api/bookings/")
        assert response.status_code == 200
        assert response.json() == [created]

    def test_unknown_room_filter_returns_404(self, client: TestClient) -> None:
        """A nonexistent room filter is reported explicitly."""
        assert_error(
            client.get("/api/bookings/", params={"room_id": "ffffffff-ffff-4fff-8fff-ffffffffffff"}),
            status=404,
            error_type="http_error",
        )

    def test_reversed_date_range_returns_422(self, client: TestClient) -> None:
        """Reversed query boundaries use the HTTP error envelope."""
        response = client.get(
            "/api/bookings/",
            params={
                "start_from": "2099-01-02T10:00:00Z",
                "start_to": "2099-01-01T10:00:00Z",
            },
        )
        error = assert_error(response, status=422, error_type="http_error")
        assert error["details"] == []
        assert error["message"]


class TestRooms:
    """Check the immutable room catalog."""

    def test_lists_rooms(self, client: TestClient) -> None:
        """The room list includes all fixed rooms."""
        response = client.get("/api/rooms/")
        assert response.status_code == 200
        assert response.json() == [
            {"id": "824f2fde-0cfb-4354-83a8-181e7b372aa6", "name": "Atlas"},
            {"id": "0dcf120a-73a6-4cad-871b-c325ce2f4beb", "name": "Orion"},
            {"id": "a2213fc6-bbc0-49d2-95dc-50742a0bf735", "name": "Vector"},
        ]

    def test_gets_one_room(self, client: TestClient) -> None:
        """A known room is individually accessible."""
        response = client.get("/api/rooms/0dcf120a-73a6-4cad-871b-c325ce2f4beb")
        assert response.status_code == 200
        assert response.json() == {"id": "0dcf120a-73a6-4cad-871b-c325ce2f4beb", "name": "Orion"}

    def test_rejects_unknown_room(self, client: TestClient) -> None:
        """A missing room returns the standard 404 envelope."""
        assert_error(client.get("/api/rooms/ffffffff-ffff-4fff-8fff-ffffffffffff"), status=404, error_type="http_error")


class TestFrameworkErrors:
    """Tests for framework error responses and validation boundaries."""

    def test_unknown_route(self, client: TestClient) -> None:
        """An unknown route returns the unified 404 envelope with no field details."""
        response = client.get("/does-not-exist")
        error = assert_error(response, status=404, error_type="http_error")
        assert error["details"] == []
        assert error["message"] == "Not Found"

    def test_method_not_allowed_preserves_allow(self, client: TestClient) -> None:
        """An unsupported method returns the unified 405 envelope and preserves the Allow header."""
        response = client.delete("/api/rooms/")
        error = assert_error(response, status=405, error_type="http_error")
        assert error["details"] == []
        assert "GET" in response.headers["allow"]
        assert error["message"] == "Method Not Allowed"

    def test_malformed_json(self, client: TestClient) -> None:
        """Malformed JSON returns a 422 validation envelope with body error locations."""
        response = client.post("/api/bookings/", content='{"title":', headers={"Content-Type": "application/json"})
        error = assert_error(response, status=422, error_type="validation_error")
        assert error["message"] == "One or more fields are invalid."
        assert error["details"]
        assert all(item["field"].startswith("body.") for item in error["details"])

    def test_validation_does_not_echo_secret(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """An invalid private code is identified by field path without exposing its input value."""
        payload = {**valid_create_json, "internal_code": {"secret": "do-not-echo-this-value"}}
        response = client.post("/api/bookings/", json=payload)
        error = assert_error(response, status=422, error_type="validation_error")
        assert "do-not-echo-this-value" not in response.text
        assert any(item["field"] == "body.internal_code" for item in error["details"])

    def test_historical_title_update(self, client: TestClient, repository: BookingRepository) -> None:
        """Updating the title of a historical booking does not rerun create-only time validation."""
        start = datetime.now(UTC) - timedelta(days=2)
        saved = repository.add(
            {
                "room_id": UUID("824f2fde-0cfb-4354-83a8-181e7b372aa6"),
                "title": "Old",
                "email": "test@example.com",
                "phone": "+123456789",
                "start_time": start,
                "end_time": start + timedelta(hours=1),
                "notes": None,
                "internal_code": "private",
            }
        )
        response = client.patch(f"/api/bookings/{saved.id}", json={"title": "Archive"})
        assert response.status_code == 200
        assert response.json()["title"] == "Archive"


class TestUUIDIdentifiers:
    """Tests for UUID validation in path, query and body parameters."""

    @pytest.mark.parametrize("path", ["/api/rooms/not-a-uuid", "/api/bookings/not-a-uuid"])
    def test_malformed_path_id(self, client: TestClient, path: str) -> None:
        """A malformed room or booking UUID returns 422 with a path error location."""
        error = assert_error(client.get(path), status=422, error_type="validation_error")
        assert any(detail["field"].startswith("path.") for detail in error["details"])

    def test_malformed_patch_id(self, client: TestClient) -> None:
        """PATCH rejects a malformed booking UUID with the validation error envelope."""
        assert_error(
            client.patch("/api/bookings/not-a-uuid", json={"title": "Title"}),
            status=422,
            error_type="validation_error",
        )

    def test_malformed_room_filter(self, client: TestClient) -> None:
        """A malformed room filter returns 422 with the query.room_id error location."""
        error = assert_error(
            client.get("/api/bookings/", params={"room_id": "not-a-uuid"}),
            status=422,
            error_type="validation_error",
        )
        assert any(detail["field"] == "query.room_id" for detail in error["details"])

    def test_malformed_room_in_body(self, client: TestClient, valid_create_json: dict[str, Any]) -> None:
        """A malformed room UUID on creation returns 422 with the body.room_id error location."""
        error = assert_error(
            client.post("/api/bookings/", json={**valid_create_json, "room_id": "not-a-uuid"}),
            status=422,
            error_type="validation_error",
        )
        assert any(detail["field"] == "body.room_id" for detail in error["details"])


class TestOpenAPI:
    """Tests for the booking request and response contracts in OpenAPI."""

    def test_creation_and_response_have_different_schemas(self, client: TestClient) -> None:
        """Creation uses a separate schema that accepts the private code but no server-generated id."""
        schema = client.get("/openapi.json").json()
        operation = schema["paths"]["/api/bookings/"]["post"]
        request_ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        response_ref = operation["responses"]["201"]["content"]["application/json"]["schema"]["$ref"]
        assert request_ref != response_ref
        request_fields = schema["components"]["schemas"][request_ref.rsplit("/", 1)[-1]]["properties"]
        assert "internal_code" in request_fields
        assert "id" not in request_fields

    def test_response_schema_exposes_only_public_booking_data(self, client: TestClient) -> None:
        """The response schema includes the id and computed fields, but never the private code."""
        schema = client.get("/openapi.json").json()
        response_ref = schema["paths"]["/api/bookings/"]["post"]["responses"]["201"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        fields = schema["components"]["schemas"][response_ref.rsplit("/", 1)[-1]]["properties"]
        assert {"id", "duration", "price"} <= fields.keys()
        assert "internal_code" not in fields
