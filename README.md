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
make install    # uv sync
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

### `app/models.py`

1. Define the `E.164` phone regex and the set of rejected characters.
2. `BookingBase` — declare the shared fields, then add:
   - a `title` validator: trim, reject empty or reserved-character titles, limit the max length.
   - a `phone` validator: enforce E.164 format.
   - a `notes` validator: trim, reject reserved characters, limit the max length.
   - a `model_validator(mode="after")`: reject a past `start_time`; require
     `end_time` at least 15 minutes after `start_time`.
3. `BookingCreateRequest` — add the sensitive `internal_code` field.
4. `BookingUpdateRequest` — same fields, all optional; reuse the validators;
   check the time window only when both times are present.
5. `BookingResponse` — declare only public fields; add a `field_serializer` that masks the phone; add
   `computed_field`s for `duration` (minutes) and `price`.

### `app/errors.py`

6. `build_error_body` — return the envelope shown below.
7. `handle_validation_error` — map `RequestValidationError` onto that envelope, with HTTP `422`.
8. `handle_http_exception` — map any `HTTPException` onto the same envelope, keeping its status code.

### `app/main.py`

9. Register your exception handlers.
10. `POST /api/bookings/` — create a booking; return it with HTTP `201`, or `409` if
    its time overlaps an existing booking.
11. `GET /api/bookings/{booking_id}` — return a booking or raise `404`.
12. `PATCH /api/bookings/{booking_id}` — apply a partial update; raise `404` if the
    booking is absent, or`409` if its new time overlaps another booking.
13. `GET /api/bookings/` — list with `limit`, `offset`, `start_from`,
    `start_to`.

## Target contract

A successful response omits `internal_code`, masks the phone, and
includes the computed fields:

```json
{
  "id": "a1b2c3d4-...",
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

Every failure uses one envelope:

```json
{
  "error": {
    "type": "validation_error",
    "message": "One or more fields are invalid.",
    "details": [
      {"field": "start_time", "issue": "Field 'start_time' must not be in the past."}
    ]
  }
}
```

## API

| Method | Path | Action |
| --- | --- | --- |
| `POST` | `/api/bookings/` | Create a booking. Returns `201`, or `409` on a time overlap. |
| `GET` | `/api/bookings/{booking_id}` | Fetch a booking. Returns `404` if absent. |
| `PATCH` | `/api/bookings/{booking_id}` | Partially update a booking. Returns `404` if absent, `409` on a time overlap. |
| `GET` | `/api/bookings/` | List bookings. Supports `limit`, `offset`, `start_from`, `start_to`. |
| `GET` | `/health` | Report service liveness. |

## Verification and grading

```bash
make test    # pytest, reports line coverage of app/
make style   # ruff format + ruff check + mypy + bandit
make all     # clean, style, then test
```

Both are expected to fail on a fresh checkout and pass once you finish every
`# TODO`. Every push and pull request runs the same checks on GitHub Actions
([.github/workflows/ci.yml](.github/workflows/ci.yml)).

Run `make help` for the full command list. Install the git hooks once with
`uv run pre-commit install`.
