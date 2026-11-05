"""Sign-in throttling: too many recent failures for a username or an address gets 429.

Kept in memory, which suits the single server process this app runs as. A restart
clears it, which is acceptable for a handful of users.
"""

import time
from collections import defaultdict, deque
from collections.abc import Callable

WINDOW_SECONDS = 15 * 60
MAX_PER_USERNAME = 5
MAX_PER_ADDRESS = 20


class LoginThrottle:
    def __init__(
        self,
        *,
        window: float = WINDOW_SECONDS,
        per_username: int = MAX_PER_USERNAME,
        per_address: int = MAX_PER_ADDRESS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.window = window
        self.limits = {"user": per_username, "addr": per_address}
        self.clock = clock
        self._failures: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _recent(self, key: tuple[str, str]) -> deque[float]:
        times = self._failures[key]
        cutoff = self.clock() - self.window
        while times and times[0] <= cutoff:
            times.popleft()
        return times

    def _keys(self, username: str, address: str) -> list[tuple[str, str]]:
        return [("user", username.strip().lower()), ("addr", address)]

    def blocked(self, username: str, address: str) -> bool:
        return any(len(self._recent(k)) >= self.limits[k[0]] for k in self._keys(username, address))

    def failed(self, username: str, address: str) -> None:
        now = self.clock()
        for key in self._keys(username, address):
            self._recent(key).append(now)

    def succeeded(self, username: str) -> None:
        self._failures.pop(("user", username.strip().lower()), None)
