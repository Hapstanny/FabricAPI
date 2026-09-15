"""Client exceptions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class FabricApiError(Exception):
    """Base exception for this package."""


class AuthenticationConfigurationError(FabricApiError):
    """Raised when authentication environment variables are invalid."""


@dataclass(slots=True)
class ApiError(FabricApiError):
    """A non-success response from a Fabric or Power BI API."""

    status_code: int
    method: str
    url: str
    code: str | None = None
    message: str | None = None
    request_id: str | None = None
    details: Any = None

    def __str__(self) -> str:
        summary = self.message or "API request failed"
        code = f" [{self.code}]" if self.code else ""
        request_id = f" (request ID: {self.request_id})" if self.request_id else ""
        return f"{self.status_code} {self.method} {self.url}{code}: {summary}{request_id}"


class ActivityWindowError(FabricApiError, ValueError):
    """Raised when an activity-events query uses an unsupported time window."""


@dataclass(slots=True)
class ApiTransportError(FabricApiError):
    """Raised when a request cannot reach the service after retries."""

    method: str
    url: str
    message: str

    def __str__(self) -> str:
        return f"{self.method} {self.url}: {self.message}"
