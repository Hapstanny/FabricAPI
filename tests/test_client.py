from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from azure.core.credentials import AccessToken

from fabric_api.client import (
    FABRIC_SCOPE,
    POWER_BI_SCOPE,
    FabricClient,
    PowerBIClient,
    _retry_delay,
)
from fabric_api.errors import ActivityWindowError, ApiError


class FakeCredential:
    def __init__(self) -> None:
        self.scopes: list[str] = []

    def get_token(self, *scopes: str, **_: object) -> AccessToken:
        self.scopes.extend(scopes)
        return AccessToken("test-token", 4_102_444_800)


def test_lists_items_with_type_and_follows_continuation_uri() -> None:
    credential = FakeCredential()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "one",
                            "displayName": "Sales",
                            "type": "Lakehouse",
                            "workspaceId": "workspace",
                        }
                    ],
                    "continuationUri": "https://api.fabric.microsoft.com/v1/next-page",
                },
            )
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "two",
                        "displayName": "Finance",
                        "type": "Lakehouse",
                        "workspaceId": "workspace",
                    }
                ]
            },
        )

    with FabricClient(credential, transport=httpx.MockTransport(handler)) as client:
        items = client.list_items("workspace", item_type="Lakehouse")

    assert [item.id for item in items] == ["one", "two"]
    assert requests[0].url.params["type"] == "Lakehouse"
    assert str(requests[1].url) == "https://api.fabric.microsoft.com/v1/next-page"
    assert credential.scopes == [FABRIC_SCOPE, FABRIC_SCOPE]
    assert requests[0].headers["Authorization"].startswith("Bearer ")
    assert requests[0].headers["Authorization"].endswith("test-token")


def test_retries_retryable_response_and_honors_retry_after() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"value": []})

    with FabricClient(
        FakeCredential(),
        transport=httpx.MockTransport(handler),
        sleep=delays.append,
    ) as client:
        assert client.list_workspaces() == []

    assert attempts == 2
    assert delays == [2.0]


def test_invalid_retry_after_uses_exponential_fallback() -> None:
    response = httpx.Response(429, headers={"Retry-After": "not a date"})

    assert 1.0 <= _retry_delay(response, attempt=0) <= 1.25


def test_naive_retry_after_date_is_treated_as_utc() -> None:
    response = httpx.Response(429, headers={"Retry-After": "Sun, 06 Nov 1994 08:49:37"})

    assert _retry_delay(response, attempt=0) == 0.0


def test_retries_transport_error_then_succeeds() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectError("connection reset", request=request)
        return httpx.Response(200, json={"value": []})

    with FabricClient(
        FakeCredential(),
        transport=httpx.MockTransport(handler),
        sleep=delays.append,
    ) as client:
        assert client.list_workspaces() == []

    assert attempts == 2
    assert len(delays) == 1


def test_raises_explicit_api_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={"requestId": "request-123"},
            json={"errorCode": "Forbidden", "message": "Access denied"},
        )

    with (
        FabricClient(FakeCredential(), transport=httpx.MockTransport(handler)) as client,
        pytest.raises(ApiError) as caught,
    ):
        client.list_capacities()

    assert caught.value.status_code == 403
    assert caught.value.code == "Forbidden"
    assert caught.value.request_id == "request-123"


def test_domains_uses_paginated_core_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"value": [{"id": "domain-one"}]})

    with FabricClient(FakeCredential(), transport=httpx.MockTransport(handler)) as client:
        assert client.list_domains() == [{"id": "domain-one"}]

    assert requests[0].url.path == "/v1/domains"


def test_queries_pipeline_activity_runs() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=[{"activityName": "Copy data"}])

    with FabricClient(FakeCredential(), transport=httpx.MockTransport(handler)) as client:
        result = client.query_pipeline_activity_runs(
            "workspace",
            "job",
            last_updated_after=datetime(2026, 9, 14, tzinfo=timezone.utc),
            last_updated_before=datetime(2026, 9, 15, tzinfo=timezone.utc),
        )

    assert result == [{"activityName": "Copy data"}]
    assert requests[0].method == "POST"
    assert requests[0].url.path.endswith("/datapipelines/pipelineruns/job/queryactivityruns")
    assert requests[0].read()
    assert b'"lastUpdatedAfter":"2026-09-14T00:00:00.000Z"' in requests[0].content


def test_activity_events_use_power_bi_scope_and_encoded_quoted_dates() -> None:
    credential = FakeCredential()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"activityEventEntities": []})

    def now() -> datetime:
        return datetime(2026, 9, 15, tzinfo=timezone.utc)

    with PowerBIClient(
        credential,
        transport=httpx.MockTransport(handler),
        now=now,
    ) as client:
        result = client.list_activity_events(
            datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc),
            datetime(2026, 9, 14, 23, 59, 59, tzinfo=timezone.utc),
        )

    assert result == []
    assert credential.scopes == [POWER_BI_SCOPE]
    assert requests[0].url.params["startDateTime"] == "'2026-09-14T00:00:00.000Z'"
    assert requests[0].url.params["endDateTime"] == "'2026-09-14T23:59:59.000Z'"


def test_activity_events_reject_cross_day_window() -> None:
    with (
        PowerBIClient(
            FakeCredential(),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json={})),
        ) as client,
        pytest.raises(ActivityWindowError, match="same UTC day"),
    ):
        client.list_activity_events(
            datetime(2026, 9, 13, 23, tzinfo=timezone.utc),
            datetime(2026, 9, 14, 1, tzinfo=timezone.utc),
        )
