from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

import pytest
import requests
from azure.core.credentials import AccessToken

from fabric_api.client import FABRIC_AUDIENCE, FabricClient, PowerBIClient, RestApiError


class Credential:
    def get_token(
        self,
        *scopes: str,
        claims: str | None = None,
        tenant_id: str | None = None,
        enable_cae: bool = False,
        **kwargs: Any,
    ) -> AccessToken:
        assert len(scopes) == 1
        return AccessToken("test-token", 0)


def response(
    status: int, payload: dict[str, object], url: str = "https://example.test/v1/workspaces"
) -> requests.Response:
    value = requests.Response()
    value.status_code, value.url = status, url
    value._content = json.dumps(payload).encode()
    return value


def test_paginates_and_uses_configured_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    session = requests.Session()
    replies = iter(
        [
            response(200, {"value": [{"id": "one"}], "continuationUri": "https://next.test"}),
            response(200, {"value": [{"id": "two"}]}),
        ]
    )
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def request(*args: object, **kwargs: object) -> requests.Response:
        calls.append((args, kwargs))
        return next(replies)

    monkeypatch.setattr(session, "request", request)
    client = FabricClient(Credential(), "https://example.test/v1", session=session)

    assert client.audience == FABRIC_AUDIENCE
    assert list(client.workspaces()) == [{"id": "one"}, {"id": "two"}]
    assert calls[0][0][1] == "https://example.test/v1/workspaces"
    assert isinstance(calls[0][1]["headers"], dict)
    assert calls[0][1]["headers"]["Authorization"].endswith("test-token")
    assert calls[1][0][1] == "https://next.test"


def test_retries_throttling_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    session = requests.Session()
    replies = iter([response(429, {"error": "busy"}), response(200, {"value": []})])
    monkeypatch.setattr(session, "request", lambda *args, **kwargs: next(replies))
    monkeypatch.setattr("fabric_api.client.time.sleep", lambda _: None)

    assert list(FabricClient(Credential(), session=session).workspaces()) == []


def test_retries_transport_failure_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    session = requests.Session()
    replies: list[requests.Response | requests.RequestException] = [
        requests.ConnectionError("offline"),
        response(200, {"value": []}),
    ]

    def request(*args: object, **kwargs: object) -> requests.Response:
        result = replies.pop(0)
        if isinstance(result, requests.RequestException):
            raise result
        return result

    monkeypatch.setattr(session, "request", request)
    monkeypatch.setattr("fabric_api.client.time.sleep", lambda _: None)
    assert list(FabricClient(Credential(), session=session).workspaces()) == []


def test_raises_explicit_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    session = requests.Session()
    monkeypatch.setattr(
        session, "request", lambda *args, **kwargs: response(403, {"error": "denied"})
    )

    with pytest.raises(RestApiError, match="403"):
        list(FabricClient(Credential(), session=session).workspaces())


def test_api_error_retains_response_and_retry_delay_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = requests.Session()
    busy = response(429, {"error": "busy"})
    busy.headers["Retry-After"] = "999"
    replies = iter([busy, response(403, {"error": "denied"})])
    delays: list[float] = []
    monkeypatch.setattr(session, "request", lambda *args, **kwargs: next(replies))
    monkeypatch.setattr("fabric_api.client.time.sleep", delays.append)

    with pytest.raises(RestApiError) as error:
        list(FabricClient(Credential(), session=session, max_retry_delay=5).workspaces())

    assert delays == [5]
    assert error.value.response is not None


@pytest.mark.parametrize(
    ("operation", "expected_path"),
    [
        (lambda client: client.capacities(), "capacities"),
        (lambda client: client.domains(), "domains"),
        (lambda client: client.deployment_pipelines(), "deploymentPipelines"),
        (
            lambda client: client.pipeline_runs("workspace", "pipeline"),
            "workspaces/workspace/items/pipeline/jobs/instances",
        ),
    ],
)
def test_fabric_typed_operations(
    monkeypatch: pytest.MonkeyPatch,
    operation: Callable[[FabricClient], Iterable[dict[str, Any]]],
    expected_path: str,
) -> None:
    session = requests.Session()
    urls: list[str] = []

    def request(*args: object, **kwargs: object) -> requests.Response:
        assert isinstance(args[1], str)
        urls.append(args[1])
        return response(200, {"value": []})

    monkeypatch.setattr(session, "request", request)
    assert (
        list(operation(FabricClient(Credential(), "https://example.test/v1", session=session)))
        == []
    )
    assert urls == [f"https://example.test/v1/{expected_path}"]


@pytest.mark.parametrize(
    ("operation", "expected_path"),
    [
        (lambda client: client.gateways(), "gateways"),
        (lambda client: client.data_sources("gateway"), "gateways/gateway/datasources"),
        (
            lambda client: client.activity_events("start", "end"),
            "admin/activityevents",
        ),
    ],
)
def test_power_bi_operations(
    monkeypatch: pytest.MonkeyPatch,
    operation: Callable[[PowerBIClient], Iterable[dict[str, Any]]],
    expected_path: str,
) -> None:
    session = requests.Session()
    urls: list[str] = []

    def request(*args: object, **kwargs: object) -> requests.Response:
        assert isinstance(args[1], str)
        urls.append(args[1])
        return response(200, {"value": []})

    monkeypatch.setattr(session, "request", request)
    assert (
        list(operation(PowerBIClient(Credential(), "https://example.test", session=session))) == []
    )
    assert urls == [f"https://example.test/{expected_path}"]
