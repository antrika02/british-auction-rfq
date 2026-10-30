from collections.abc import Callable
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_clock() -> Callable[[], datetime]:
    """FastAPI dependency. Tests replace this to control time."""
    return utcnow
