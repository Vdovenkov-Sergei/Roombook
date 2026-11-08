# Roombook

A contract-driven meeting-room booking API. You implement it with `FastAPI` and
`Pydantic`, following an explicit request/response contract. Storage is
_in-memory_ — no database required.

## Requirements

- Programming language interpreter — [Python 3.14](https://www.python.org/downloads/)
- Fast Python package and project manager — [uv](https://docs.astral.sh/uv/)
- Build automation and task runner — [GNU Make](https://www.gnu.org/software/make/)

## Quickstart

```bash
make install    # uv sync --locked
make run        # uvicorn app.main:app --reload
```

Open the API docs at http://127.0.0.1:8000/docs.

The starter is incomplete. `make test` fails until you implement the `# TODO`
blocks in `app/`.

## Layout

| Path | Purpose |
| --- | --- |
| `app/` | The service you implement. Complete parts are given; incomplete parts are marked `# TODO`. |
| `tests/` | The test suite that grades your implementation. Do not edit it. |

## Task

Implement every `# TODO` in `app/models.py`, `app/errors.py`, and `app/main.py`.
The repositories (`app/bookings.py`, `app/rooms.py`), constants and business
exceptions are already implemented; do not modify them or the tests.

### `app/models.py`

1. Define the `E.164` phone regex: `+`, then 8–15 ASCII digits, first digit non-zero.
2. `BookingBase` — declare `room_id`, `title`, `email`, `phone`, `start_time`, `end_time`,
   and optional `notes`, then add:
   - a `title` validator: trim, reject empty titles, limit the max length.
   - a `phone` validator: enforce E.164 format.
   - a `notes` validator: trim, normalize blank notes to `None`, limit the max length.
3. `BookingCreateRequest` — add the required, nonempty `internal_code` field,
   excluded from `repr`; add a `model_validator(mode="after")` requiring
   `start_time` in the future and `end_time` at least 15 minutes later.
4. `BookingUpdateRequest` — editable fields only (`title`, `email`, `phone`,
   `start_time`, `end_time`, `notes`), all omittable; reuse the validators.
   Reject explicit `null` except for `notes`, where it clears the value.
   A supplied `start_time` must be in the future; check the time window when
   both times are present. The repository checks the merged interval otherwise.
5. `BookingResponse` — declare only public fields; add a `field_serializer` that masks the phone; add
   `computed_field`s for `duration` (minutes) and `price`.

### `app/errors.py`

6. `build_error_body` — return the envelope shown below.
7. `handle_validation_error` — map `RequestValidationError` onto that envelope, with HTTP `422`.
8. `handle_http_exception` — map any `HTTPException` onto the same envelope, keeping its status code and headers.

### `app/main.py`

9. Register your exception handlers.
10. `GET /api/rooms/{room_id}` — return a room or raise `404`.
11. `POST /api/bookings/` — create a booking; return it with HTTP `201`, or `409` if
    its time overlaps an existing booking in the same room; an unknown room gives `404`.
12. `GET /api/bookings/{booking_id}` — return a booking or raise `404`.
13. `PATCH /api/bookings/{booking_id}` — apply a partial update; raise `404` if the
    booking is absent, `409` if its new time overlaps another booking in the same
    room, or `422` if the merged time window is too short.
14. `GET /api/bookings/` — list with `limit`, `offset`, `start_from`,
    `start_to`, and optional `room_id`; reject a reversed time range with `422`.

## Target contract

A successful response omits `internal_code`, masks the phone, and
includes the computed fields:

```json
{
  "id": "eba92425-47c6-4d8b-a9c7-c4d181233026",
  "room_id": "824f2fde-0cfb-4354-83a8-181e7b372aa6",
  "title": "title",
  "email": "email@example.com",
  "phone": "********2671",
  "start_time": "2099-01-02T09:00:00Z",
  "end_time": "2099-01-02T10:00:00Z",
  "notes": "text",
  "created_at": "2099-01-01T12:00:00Z",
  "duration": 60,
  "price": 25.0
}
```

Unknown fields are rejected. Historical bookings remain readable; adjacent bookings are allowed.

Expected client errors use one envelope:

```json
{
  "error": {
    "type": "validation_error",
    "message": "One or more fields are invalid.",
    "details": [
      {
        "field": "body",
        "issue": "Value error, Field 'start_time' must not be in the past."
      }
    ]
  }
}
```

Error fields use dot-separated paths (`body.title`, `query.limit`),
or `body` for a model-level error.

## API

| Method | Path | Action |
| --- | --- | --- |
| `GET` | `/api/rooms/` | List available rooms. |
| `GET` | `/api/rooms/{room_id}` | Fetch a room. Returns `404` if absent. |
| `POST` | `/api/bookings/` | Create a booking. Returns `201`, or `409` on a time overlap. |
| `GET` | `/api/bookings/{booking_id}` | Fetch a booking. Returns `404` if absent. |
| `PATCH` | `/api/bookings/{booking_id}` | Partially update a booking. Returns `404` if absent, `409` on a time overlap, `422` if the merged time window is too short. |
| `GET` | `/api/bookings/` | List bookings. Supports `limit`, `offset`, `start_from`, `start_to`, `room_id`. |
| `GET` | `/health` | Report service liveness. |

Start-time filter boundaries are inclusive. Filter first, sort by start time
then UUID, and paginate last. An unknown room filter gives `404`.

## Verification and grading

```bash
make test    # pytest, reports line coverage of app/
make format  # apply ruff formatting
make style   # ruff format --check + ruff check + mypy + bandit
make all     # clean, style, then test
```

Tests are expected to fail on a fresh checkout. Tests and quality checks must
pass once you finish every `# TODO`. Every push and pull request runs the same checks on GitHub Actions
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

Run `make help` for the full command list. Install the git hooks once with
`uv run pre-commit install`.
