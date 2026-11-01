"""Errors raised by the external catalogue clients. Messages never include URLs or keys."""

from typing import Literal

Source = Literal["tmdb", "omdb"]


class ExternalApiError(Exception):
    """A TMDB/OMDb call failed: HTTP error status, timeout or connection error."""

    def __init__(self, source: Source, status: int | None) -> None:
        self.source = source
        self.status = status  # None = network error or timeout
        super().__init__(f"{source} request failed ({status if status is not None else 'network'})")


class ExternalNotFound(ExternalApiError):
    """The external source answered 404."""
