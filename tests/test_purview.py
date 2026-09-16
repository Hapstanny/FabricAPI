from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
from azure.core.credentials import AccessToken

from fabric_api.models import AuditLogQueryFilters
from fabric_api.purview import GRAPH_SCOPE, PurviewAuditClient


class FakeCredential:
    def __init__(self) -> None:
        self.scopes: list[str] = []

    def get_token(self, *scopes: str, **_: object) -> AccessToken:
        self.scopes.extend(scopes)
        return AccessToken("graph-token", 4_102_444_800)


def _filters() -> AuditLogQueryFilters:
    return AuditLogQueryFilters(
        filter_start=datetime(2026, 9, 1, tzinfo=timezone.utc),
        filter_end=datetime(2026, 9, 2, tzinfo=timezone.utc),
        display_name="Governance export",
        record_type_filters=("powerBIAudit",),
        service_filter="PowerBI",
        operation_filters=("CopilotInteraction",),
        user_principal_name_filters=("analyst@example.com",),
        ip_address_filters=("192.0.2.1",),
        object_id_filters=("report-id",),
        keyword_filter="governance",
    )


def test_graph_query_polling_and_odata_pagination() -> None:
    credential = FakeCredential()
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx.Response(201, json={"id": "query-1", "status": "running"})
        if request.url.path.endswith("/query-1"):
            return httpx.Response(200, json={"id": "query-1", "status": "succeeded"})
        if request.url.params.get("$skiptoken"):
            return httpx.Response(
                200,
                json={
                    "value": [
                        {
                            "id": "record-2",
                            "operation": "ViewReport",
                            "auditData": {"Activity": "ViewReport"},
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "value": [
                    {
                        "id": "record-1",
                        "operation": "CopilotInteraction",
                        "auditData": {"CopilotEventData": {"AppHost": "PowerBI"}},
                    }
                ],
                "@odata.nextLink": (
                    "https://graph.microsoft.com/v1.0/security/auditLog/"
                    "queries/query-1/records?$skiptoken=next"
                ),
            },
        )

    sleeps: list[float] = []
    with PurviewAuditClient(
        credential,
        transport=httpx.MockTransport(handler),
        sleep=sleeps.append,
        monotonic=lambda: 0.0,
    ) as client:
        result = client.run_query(_filters(), poll_interval=2, poll_timeout=30)

    assert result.complete is True
    assert [record.id for record in result.records] == ["record-1", "record-2"]
    assert sleeps == [2]
    assert credential.scopes == [GRAPH_SCOPE]
    assert requests[0].url == "https://graph.microsoft.com/v1.0/security/auditLog/queries"
    payload = requests[0].read().decode()
    assert '"recordTypeFilters":["powerBIAudit"]' in payload
    assert '"serviceFilter":"PowerBI"' in payload
    assert '"operationFilters":["CopilotInteraction"]' in payload
    assert requests[-1].headers["Authorization"] == "Bearer graph-token"


def test_query_failure_is_returned_as_incomplete() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "query-1", "status": "failed"})

    with PurviewAuditClient(
        FakeCredential(),
        transport=httpx.MockTransport(handler),
    ) as client:
        result = client.run_query(_filters())

    assert result.complete is False
    assert result.query.status == "failed"
    assert result.errors == ("Audit query completed with status failed",)


def test_query_poll_timeout_is_returned_as_incomplete() -> None:
    times = iter((0.0, 2.0))

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "query-1", "status": "running"})

    with PurviewAuditClient(
        FakeCredential(),
        transport=httpx.MockTransport(handler),
        monotonic=lambda: next(times),
    ) as client:
        result = client.run_query(_filters(), poll_timeout=1)

    assert result.complete is False
    assert "timed out" in result.errors[0]


def test_query_poll_api_error_is_returned_as_incomplete() -> None:
    requests = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        if requests == 1:
            return httpx.Response(201, json={"id": "query-1", "status": "running"})
        return httpx.Response(503, json={"error": {"code": "Unavailable", "message": "Later"}})

    with PurviewAuditClient(
        FakeCredential(),
        transport=httpx.MockTransport(handler),
        max_retries=0,
        sleep=lambda _: None,
        monotonic=lambda: 0.0,
    ) as client:
        result = client.run_query(_filters(), poll_timeout=1)

    assert result.complete is False
    assert "status polling failed" in result.errors[0]
    assert "503 GET" in result.errors[0]


def test_query_filters_reject_naive_or_reversed_timestamps() -> None:
    with pytest.raises(ValueError, match="UTC offset"):
        AuditLogQueryFilters(
            filter_start=datetime(2026, 9, 1),
            filter_end=datetime(2026, 9, 2, tzinfo=timezone.utc),
        )
    with pytest.raises(ValueError, match="later"):
        AuditLogQueryFilters(
            filter_start=datetime(2026, 9, 2, tzinfo=timezone.utc),
            filter_end=datetime(2026, 9, 1, tzinfo=timezone.utc),
        )
