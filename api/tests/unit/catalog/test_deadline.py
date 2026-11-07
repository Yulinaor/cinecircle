"""The per-request deadline (plan P8): a chain of TMDB/OMDb calls shares one time budget."""

from types import SimpleNamespace

import httpx
import pytest

from cinecircle_api.catalog import _http
from cinecircle_api.catalog._http import MIN_CALL_S, REQUEST_BUDGET_S, TIMEOUT_S, deadline, get_json
from cinecircle_api.catalog.errors import ExternalApiError


class FakeClock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class RecordingHttp:
    """Stands in for httpx.Client: records the timeout each call was given."""

    def __init__(self, clock: FakeClock | None = None, call_takes: float = 0.0) -> None:
        self.timeouts: list[float] = []
        self._clock = clock
        self._call_takes = call_takes

    def get(self, url, params=None, headers=None, timeout=None) -> httpx.Response:
        self.timeouts.append(timeout)
        if self._clock is not None:
            self._clock.now += self._call_takes
        return httpx.Response(200, json={"ok": True})


@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(_http, "time", SimpleNamespace(monotonic=fake))
    return fake


def call(http: RecordingHttp) -> dict:
    return get_json(http, "tmdb", "https://example.test/x", {})  # type: ignore[arg-type]


def test_constants():
    assert REQUEST_BUDGET_S == 10.0
    assert MIN_CALL_S == 0.2


def test_no_deadline_keeps_the_per_call_timeout():
    http = RecordingHttp()
    call(http)
    assert http.timeouts == [TIMEOUT_S]


def test_deadline_shrinks_the_timeout(clock):
    http = RecordingHttp()
    with deadline(10.0):
        clock.now += 1.0  # 9 s left: the 5 s per-call cap still applies
        call(http)
        clock.now += 6.0  # 3 s left
        call(http)
    assert http.timeouts == [TIMEOUT_S, pytest.approx(3.0)]


def test_deadline_expired_skips_the_call(clock):
    http = RecordingHttp()
    with deadline(10.0):
        clock.now += 9.9  # 0.1 s left, under MIN_CALL_S
        with pytest.raises(ExternalApiError) as info:
            call(http)
    assert http.timeouts == []
    assert info.value.source == "tmdb" and info.value.status is None


def test_nested_deadline_keeps_the_earliest(clock):
    http = RecordingHttp()
    with deadline(2.0):
        with deadline(10.0):
            call(http)
    assert http.timeouts == [pytest.approx(2.0)]


def test_inner_deadline_can_be_shorter(clock):
    http = RecordingHttp()
    with deadline(10.0):
        with deadline(1.0):
            call(http)
        call(http)  # the outer budget is back
    assert http.timeouts == [pytest.approx(1.0), TIMEOUT_S]


def test_deadline_is_cleared_on_exit(clock):
    http = RecordingHttp()
    with pytest.raises(RuntimeError):
        with deadline(1.0):
            raise RuntimeError
    clock.now += 50.0
    call(http)
    assert http.timeouts == [TIMEOUT_S]


def test_a_slow_chain_stops_when_the_budget_is_spent(clock):
    http = RecordingHttp(clock, call_takes=4.0)
    with deadline(10.0):
        call(http)  # 10 s left -> 5 s timeout
        call(http)  # 6 s left -> 5 s
        call(http)  # 2 s left -> 2 s
        with pytest.raises(ExternalApiError):
            call(http)  # -2 s left
    assert http.timeouts == [TIMEOUT_S, TIMEOUT_S, pytest.approx(2.0)]
