"""Business failures translated to HTTP at the application boundary."""


class BookingConflictError(Exception):
    """A time slot overlaps another booking in the same room."""


class InvalidBookingWindowError(Exception):
    """The resulting interval is shorter than the minimum duration."""
