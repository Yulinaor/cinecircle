"""Shared GET helper: turns every httpx failure into a key-safe ExternalApiError."""

import httpx

from cinecircle_api.catalog.errors import ExternalApiError, ExternalNotFound, Source

TIMEOUT_S = 5.0


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
    if response.status_code == 404:
        raise ExternalNotFound(source, 404) from None
    if response.is_error:
        raise ExternalApiError(source, response.status_code) from None
    try:
        return response.json()
    except ValueError:
        raise ExternalApiError(source, response.status_code) from None
