"""Shared GET helper: turns every httpx failure into a key-safe ExternalApiError."""

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import httpx

from cinecircle_api.catalog.errors import ExternalApiError, ExternalNotFound, Source

TIMEOUT_S = 5.0
REQUEST_BUDGET_S = 10.0  # one request's whole chain of TMDB/OMDb calls (plan P8)
MIN_CALL_S = 0.2  # less than this left: do not start another call
log = logging.getLogger(__name__)
# httpx logs each request URL at INFO, query string included; OMDb's holds the API key.
logging.getLogger("httpx").setLevel(logging.WARNING)

# Absolute time.monotonic() end of the current request's budget; None outside any deadline.
_deadline_end: ContextVar[float | None] = ContextVar("catalog_deadline_end", default=None)


@contextmanager
def deadline(seconds: float = REQUEST_BUDGET_S) -> Iterator[None]:
    """Bound every get_json call made inside to `seconds` in total. Nested deadlines keep the
    earlier end, so a caller's budget can never be extended by a callee."""
    end = time.monotonic() + seconds
    current = _deadline_end.get()
    token = _deadline_end.set(end if current is None else min(current, end))
    try:
        yield
    finally:
        _deadline_end.reset(token)


def _call_timeout(source: Source) -> float:
    end = _deadline_end.get()
    if end is None:
        return TIMEOUT_S
    remaining = end - time.monotonic()
    if remaining < MIN_CALL_S:
        raise ExternalApiError(source, None)
    return min(TIMEOUT_S, remaining)


def get_json(
    http: httpx.Client,
    source: Source,
    url: str,
    params: dict[str, str],
    headers: dict[str, str] | None = None,
) -> dict:
    timeout = _call_timeout(source)
    try:
        response = http.get(url, params=params, headers=headers, timeout=timeout)
    except httpx.HTTPError:
        # `from None`: the httpx exception's text holds the URL, and OMDb's URL holds the key.
        raise ExternalApiError(source, None) from None
    # `url` never carries the key: keys travel in `params` or `headers`.
    log.info("%s GET %s -> %s", source, url, response.status_code)
    if response.status_code == 404:
        raise ExternalNotFound(source, 404) from None
    if response.is_error:
        raise ExternalApiError(source, response.status_code) from None
    try:
        body = response.json()
    except ValueError:
        raise ExternalApiError(source, response.status_code) from None
    if not isinstance(body, dict):  # callers read it with .get
        raise ExternalApiError(source, response.status_code)
    return body
