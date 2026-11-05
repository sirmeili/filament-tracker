from filament_tracker.services.throttle import LoginThrottle


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _throttle(clock: Clock) -> LoginThrottle:
    return LoginThrottle(window=60, per_username=3, per_address=5, clock=clock)


def test_a_username_is_blocked_after_too_many_failures() -> None:
    throttle = _throttle(Clock())
    for _ in range(2):
        throttle.failed("Alice", "1.1.1.1")
    assert not throttle.blocked("alice", "2.2.2.2")

    throttle.failed("alice ", "3.3.3.3")

    assert throttle.blocked("ALICE", "4.4.4.4")
    assert not throttle.blocked("bob", "4.4.4.4")


def test_an_address_is_blocked_after_too_many_failures() -> None:
    throttle = _throttle(Clock())
    for n in range(5):
        throttle.failed(f"user{n}", "1.1.1.1")

    assert throttle.blocked("someone", "1.1.1.1")
    assert not throttle.blocked("someone", "2.2.2.2")


def test_failures_expire_after_the_window() -> None:
    clock = Clock()
    throttle = _throttle(clock)
    for _ in range(3):
        throttle.failed("alice", "1.1.1.1")

    clock.now += 60

    assert not throttle.blocked("alice", "1.1.1.1")


def test_a_success_clears_the_username_but_not_the_address() -> None:
    throttle = _throttle(Clock())
    for n in range(3):
        throttle.failed("alice", "1.1.1.1")
        throttle.failed(f"other{n}", "1.1.1.1")

    throttle.succeeded("Alice")

    assert not throttle.blocked("alice", "2.2.2.2")
    assert throttle.blocked("alice", "1.1.1.1")


def test_defaults() -> None:
    throttle = LoginThrottle()

    assert throttle.limits == {"user": 5, "addr": 20}
    assert throttle.window == 15 * 60
