"""Small reusable clients with pagination, retries, timeouts, and API errors."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import requests
from azure.core.credentials import TokenCredential

FABRIC_AUDIENCE = "https://api.fabric.microsoft.com/.default"
POWER_BI_AUDIENCE = "https://analysis.windows.net/powerbi/api/.default"


class RestApiError(requests.HTTPError):
    """An unsuccessful REST response with request context."""

    def __init__(self, response: requests.Response) -> None:
        self.status_code = response.status_code
        self.url = response.url
        try:
            self.details: Any = response.json()
        except ValueError:
            self.details = response.text
        super().__init__(
            f"API request failed ({self.status_code}) for {self.url}: {self.details}",
            response=response,
        )


class RestClient:
    def __init__(
        self,
        credential: TokenCredential,
        audience: str,
        base_url: str,
        *,
        timeout: float = 30,
        retries: int = 3,
        max_retry_delay: float = 30,
        session: requests.Session | None = None,
    ) -> None:
        self.credential = credential
        self.audience = audience
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.retries = retries
        self.max_retry_delay = max_retry_delay
        self.session = session or requests.Session()

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = (
            path_or_url
            if path_or_url.startswith(("http://", "https://"))
            else f"{self.base_url}/{path_or_url.lstrip('/')}"
        )
        for attempt in range(self.retries + 1):
            token = self.credential.get_token(self.audience)
            headers = {"Authorization": "Bearer " + token.token}
            try:
                response = self.session.request(
                    method, url, headers=headers, params=params, json=json, timeout=self.timeout
                )
            except requests.RequestException:
                if attempt == self.retries:
                    raise
                delay = min(2**attempt, self.max_retry_delay)
            else:
                if response.status_code < 400:
                    return response.json() if response.content else {}
                if response.status_code not in {429, 500, 502, 503, 504} or attempt == self.retries:
                    raise RestApiError(response)
                delay = self._retry_delay(response.headers.get("Retry-After"), attempt)
            time.sleep(delay)
        raise AssertionError("unreachable")

    def _retry_delay(self, retry_after: str | None, attempt: int) -> float:
        if retry_after:
            try:
                delay = float(retry_after)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(retry_after) - datetime.now(UTC)).total_seconds()
                except (TypeError, ValueError):
                    delay = 2**attempt
        else:
            delay = 2**attempt
        return min(max(0, delay), self.max_retry_delay)

    def list_pages(
        self, path: str, *, params: Mapping[str, str] | None = None
    ) -> Iterator[dict[str, Any]]:
        next_url: str | None = path
        next_params = params
        seen_urls: set[str] = set()
        while next_url:
            if next_url in seen_urls:
                raise ValueError(f"Repeated pagination URL: {next_url}")
            seen_urls.add(next_url)
            page = self.request("GET", next_url, params=next_params)
            yield page
            next_url = page.get("continuationUri") or page.get("@odata.nextLink")
            next_params = None

    def list_values(
        self, path: str, *, params: Mapping[str, str] | None = None
    ) -> Iterator[dict[str, Any]]:
        for page in self.list_pages(path, params=params):
            values = page.get("value", page.get("data", []))
            yield from values


class FabricClient(RestClient):
    def __init__(
        self,
        credential: TokenCredential,
        base_url: str = "https://api.fabric.microsoft.com/v1",
        **kwargs: Any,
    ) -> None:
        super().__init__(credential, FABRIC_AUDIENCE, base_url, **kwargs)

    def workspaces(self) -> Iterator[dict[str, Any]]:
        return self.list_values("workspaces")

    def items(self, workspace_id: str, item_type: str | None = None) -> Iterator[dict[str, Any]]:
        path = f"workspaces/{workspace_id}/items"
        return self.list_values(path, params={"type": item_type} if item_type else None)

    def capacities(self) -> Iterator[dict[str, Any]]:
        return self.list_values("capacities")

    def domains(self) -> Iterator[dict[str, Any]]:
        return self.list_values("domains")

    def deployment_pipelines(self) -> Iterator[dict[str, Any]]:
        return self.list_values("deploymentPipelines")

    def pipeline_runs(self, workspace_id: str, pipeline_id: str) -> Iterator[dict[str, Any]]:
        return self.list_values(f"workspaces/{workspace_id}/items/{pipeline_id}/jobs/instances")


class PowerBIClient(RestClient):
    def __init__(
        self,
        credential: TokenCredential,
        base_url: str = "https://api.powerbi.com/v1.0/myorg",
        **kwargs: Any,
    ) -> None:
        super().__init__(credential, POWER_BI_AUDIENCE, base_url, **kwargs)

    def gateways(self) -> Iterator[dict[str, Any]]:
        return self.list_values("gateways")

    def data_sources(self, gateway_id: str) -> Iterator[dict[str, Any]]:
        return self.list_values(f"gateways/{gateway_id}/datasources")

    def activity_events(self, start: str, end: str) -> Iterator[dict[str, Any]]:
        return self.list_values(
            "admin/activityevents", params={"startDateTime": start, "endDateTime": end}
        )
