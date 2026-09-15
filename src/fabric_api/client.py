"""HTTP clients for Microsoft Fabric and Power BI REST APIs."""

from __future__ import annotations

import email.utils
import random
import time
from collections.abc import Callable, Iterator, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any, cast

import httpx
from azure.core.credentials import AccessToken, TokenCredential
from typing_extensions import Self

from .errors import ActivityWindowError, ApiError, ApiTransportError
from .models import FabricItem, Page

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
POWER_BI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class RestClient:
    """Authenticated JSON REST client with bounded retries."""

    def __init__(
        self,
        credential: TokenCredential,
        *,
        scope: str,
        base_url: str,
        timeout: float = 30.0,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self._credential = credential
        self._scope = scope
        self._max_retries = max_retries
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={"Accept": "application/json", "User-Agent": "fabric-api-examples/0.1.0"},
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def get(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, object] | None = None,
    ) -> Mapping[str, Any]:
        return self.request("GET", path_or_url, params=params)

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, object] | None = None,
        json: object | None = None,
    ) -> Mapping[str, Any]:
        payload = self.request_json(method, path_or_url, params=params, json=json)
        if not isinstance(payload, Mapping):
            raise TypeError("Expected the API response to be a JSON object")
        return payload

    def request_json(
        self,
        method: str,
        path_or_url: str,
        *,
        params: Mapping[str, object] | None = None,
        json: object | None = None,
    ) -> object:
        for attempt in range(self._max_retries + 1):
            token: AccessToken = self._credential.get_token(self._scope)
            try:
                response = self._client.request(
                    method,
                    path_or_url,
                    params=params,
                    json=json,
                    headers={"Authorization": " ".join(("Bearer", token.token))},
                )
            except httpx.TransportError as error:
                if attempt == self._max_retries:
                    request_url = str(error.request.url) if error.request else path_or_url
                    raise ApiTransportError(method, request_url, str(error)) from error
                self._sleep(_exponential_delay(attempt))
                continue
            if response.status_code not in RETRYABLE_STATUS_CODES or attempt == self._max_retries:
                break
            self._sleep(_retry_delay(response, attempt))

        if response.is_error:
            raise _api_error(response)
        if response.status_code == 204:
            return {}
        return response.json()

    def iter_pages(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, object] | None = None,
        value_key: str = "value",
    ) -> Iterator[Page]:
        next_url: str | None = path_or_url
        original_params = dict(params or {})
        next_params = dict(original_params)
        while next_url:
            page = Page.from_dict(self.get(next_url, params=next_params), value_key=value_key)
            yield page
            next_params = {}
            if page.continuation_uri:
                next_url = page.continuation_uri
            elif page.continuation_token:
                next_url = path_or_url
                next_params = {
                    **original_params,
                    "continuationToken": page.continuation_token,
                }
            else:
                next_url = None

    def list_all(
        self,
        path_or_url: str,
        *,
        params: Mapping[str, object] | None = None,
        value_key: str = "value",
    ) -> list[Mapping[str, Any]]:
        return [
            item
            for page in self.iter_pages(path_or_url, params=params, value_key=value_key)
            for item in page.value
        ]


class FabricClient(RestClient):
    """Client for https://api.fabric.microsoft.com/v1."""

    def __init__(
        self,
        credential: TokenCredential,
        *,
        base_url: str = "https://api.fabric.microsoft.com",
        timeout: float = 30.0,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(
            credential,
            scope=FABRIC_SCOPE,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            transport=transport,
            sleep=sleep,
        )

    def list_workspaces(self) -> list[Mapping[str, Any]]:
        return self.list_all("/v1/workspaces")

    def list_items(
        self,
        workspace_id: str,
        *,
        item_type: str | None = None,
        recursive: bool | None = None,
        root_folder_id: str | None = None,
    ) -> list[FabricItem]:
        params: dict[str, object] = {}
        if item_type:
            params["type"] = item_type
        if recursive is not None:
            params["recursive"] = str(recursive).lower()
        if root_folder_id:
            params["rootFolderId"] = root_folder_id
        values = self.list_all(f"/v1/workspaces/{workspace_id}/items", params=params)
        return [FabricItem.from_dict(item) for item in values]

    def get_item(self, workspace_id: str, item_id: str) -> FabricItem:
        payload = self.get(f"/v1/workspaces/{workspace_id}/items/{item_id}")
        return FabricItem.from_dict(payload)

    def list_capacities(self) -> list[Mapping[str, Any]]:
        return self.list_all("/v1/capacities")

    def list_deployment_pipelines(self) -> list[Mapping[str, Any]]:
        return self.list_all("/v1/deploymentPipelines")

    def list_domains(self) -> list[Mapping[str, Any]]:
        return self.list_all("/v1/domains")

    def query_pipeline_activity_runs(
        self,
        workspace_id: str,
        job_instance_id: str,
        *,
        last_updated_after: datetime,
        last_updated_before: datetime,
    ) -> list[Mapping[str, Any]]:
        after = _as_utc(last_updated_after)
        before = _as_utc(last_updated_before)
        if before <= after:
            raise ValueError("last_updated_before must be later than last_updated_after")
        payload = self.request_json(
            "POST",
            (
                f"/v1/workspaces/{workspace_id}/datapipelines/"
                f"pipelineruns/{job_instance_id}/queryactivityruns"
            ),
            json={
                "filters": [],
                "orderBy": [{"orderBy": "ActivityRunStart", "order": "DESC"}],
                "lastUpdatedAfter": _format_iso_datetime(after),
                "lastUpdatedBefore": _format_iso_datetime(before),
            },
        )
        if not isinstance(payload, list):
            raise TypeError("Expected pipeline activity-runs response to be a JSON array")
        return [activity for activity in payload if isinstance(activity, Mapping)]


class PowerBIClient(RestClient):
    """Client for Power BI REST and Admin REST APIs."""

    def __init__(
        self,
        credential: TokenCredential,
        *,
        base_url: str = "https://api.powerbi.com",
        timeout: float = 30.0,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        super().__init__(
            credential,
            scope=POWER_BI_SCOPE,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            transport=transport,
            sleep=sleep,
        )
        self._now = now

    def list_gateways(self) -> list[Mapping[str, Any]]:
        return self.list_all("/v1.0/myorg/gateways")

    def list_datasources(self, workspace_id: str, dataset_id: str) -> list[Mapping[str, Any]]:
        return self.list_all(f"/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/datasources")

    def list_activity_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list[Mapping[str, Any]]:
        start_utc = _as_utc(start)
        end_utc = _as_utc(end)
        if end_utc <= start_utc:
            raise ActivityWindowError("end must be later than start")
        if start_utc.date() != end_utc.date():
            raise ActivityWindowError("activity-events start and end must be in the same UTC day")
        if start_utc < self._now().astimezone(timezone.utc) - timedelta(days=28):
            raise ActivityWindowError("activity-events start cannot be more than 28 days old")

        params = {
            "startDateTime": f"'{_format_power_bi_datetime(start_utc)}'",
            "endDateTime": f"'{_format_power_bi_datetime(end_utc)}'",
        }
        return self.list_all(
            "/v1.0/myorg/admin/activityevents",
            params=params,
            value_key="activityEventEntities",
        )


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            try:
                parsed = email.utils.parsedate_to_datetime(retry_after)
            except (TypeError, ValueError, OverflowError):
                parsed = None
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                seconds = (parsed - datetime.now(timezone.utc)).total_seconds()
                return max(0.0, seconds)
    return _exponential_delay(attempt)


def _exponential_delay(attempt: int) -> float:
    return cast(float, min(30.0, (2**attempt) + random.uniform(0.0, 0.25)))


def _api_error(response: httpx.Response) -> ApiError:
    code: str | None = None
    message: str | None = None
    details: object = None
    try:
        body = response.json()
    except ValueError:
        message = response.text or response.reason_phrase
    else:
        details = body
        if isinstance(body, Mapping):
            error = body.get("error", body)
            if isinstance(error, Mapping):
                code_value = error.get("errorCode", error.get("code"))
                message_value = error.get("message")
                code = str(code_value) if code_value is not None else None
                message = str(message_value) if message_value is not None else None
    request_id = (
        response.headers.get("requestId")
        or response.headers.get("x-ms-request-id")
        or response.headers.get("ActivityId")
    )
    return ApiError(
        status_code=response.status_code,
        method=response.request.method,
        url=str(response.request.url),
        code=code,
        message=message,
        request_id=request_id,
        details=details,
    )


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ActivityWindowError("activity-events timestamps must include a UTC offset")
    return value.astimezone(timezone.utc)


def _format_power_bi_datetime(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _format_iso_datetime(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")
