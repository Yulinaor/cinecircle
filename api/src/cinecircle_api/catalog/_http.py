"""Shared GET helper: turns every httpx failure into a key-safe ExternalApiError."""

import logging

import httpx

from cinecircle_api.catalog.errors import ExternalApiError, ExternalNotFound, Source

TIMEOUT_S = 5.0
log = logging.getLogger(__name__)
# httpx logs each request URL at INFO, query string included; OMDb's holds the API key.
logging.getLogger("httpx").setLevel(logging.WARNING)


def get_json(
    http: httpx.Client,
    source: Source,
    url: str,
    params: dict[str, str],
    headers: dict[str, str] | None = None,
) -> dict:
    try:
        response = http.get(url, params=params, headers=headers, timeout=TIMEOUT_S)
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
