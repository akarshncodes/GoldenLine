"""FR-12: rate-limit FLAGGING. Never blocks — a real emergency must always go through.

An in-process sliding window per source. When the count in the window crosses the
threshold a `rate_limit_flags` row is written for human review; the request still
proceeds.
"""
import threading
import time
from collections import defaultdict, deque

from sqlalchemy.orm import Session

from app.config import RATE_LIMIT_THRESHOLD, RATE_LIMIT_WINDOW_SECONDS
from app.models.auth import RateLimitFlag

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def reset() -> None:
    """Test hook — clear the in-memory window."""
    with _lock:
        _hits.clear()


def record_and_maybe_flag(db: Session, *, source: str, source_type: str) -> RateLimitFlag | None:
    """Record one request from `source`. Returns a flag row if the rate looks abusive."""
    now = time.monotonic()
    window = RATE_LIMIT_WINDOW_SECONDS
    with _lock:
        q = _hits[source]
        q.append(now)
        while q and q[0] < now - window:
            q.popleft()
        count = len(q)

    if count <= RATE_LIMIT_THRESHOLD:
        return None

    flag = RateLimitFlag(
        source=source,
        source_type=source_type,
        request_count=count,
        window_seconds=window,
        reviewed=False,
    )
    db.add(flag)
    db.flush()
    return flag
