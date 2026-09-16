"""Microsoft Graph v1.0 client for Microsoft Purview Audit Search."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from urllib.parse import quote

import httpx
from azure.core.credentials import TokenCredential

from .client import RestClient
from .errors import FabricApiError
from .models import (
    AuditCollectionResult,
    AuditLogQuery,
    AuditLogQueryFilters,
    AuditLogRecord,
)

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
TERMINAL_QUERY_STATUSES = frozenset({"succeeded", "failed", "cancelled", "unknownFutureValue"})


class PurviewAuditClient(RestClient):
    """Client for the Microsoft Graph v1.0 Purview Audit Search API."""

    def __init__(
        self,
        credential: TokenCredential,
        *,
        base_url: str = "https://graph.microsoft.com",
        timeout: float = 30.0,
        max_retries: int = 4,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(
            credential,
            scope=GRAPH_SCOPE,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            transport=transport,
            sleep=sleep,
        )
        self._poll_sleep = sleep
        self._monotonic = monotonic

    def create_query(self, filters: AuditLogQueryFilters) -> AuditLogQuery:
        payload = self.request(
            "POST",
            "/v1.0/security/auditLog/queries",
            json=filters.to_payload(),
        )
        return AuditLogQuery.from_dict(payload)

    def get_query(self, query_id: str) -> AuditLogQuery:
        payload = self.get(f"/v1.0/security/auditLog/queries/{quote(query_id, safe='')}")
        return AuditLogQuery.from_dict(payload)

    def iter_records(self, query_id: str) -> Iterator[AuditLogRecord]:
        path = f"/v1.0/security/auditLog/queries/{quote(query_id, safe='')}/records"
        for page in self.iter_pages(path):
            yield from (AuditLogRecord.from_dict(item) for item in page.value)

    def run_query(
        self,
        filters: AuditLogQueryFilters,
        *,
        poll_interval: float = 5.0,
        poll_timeout: float = 900.0,
    ) -> AuditCollectionResult:
        if poll_interval <= 0:
            raise ValueError("poll_interval must be greater than zero")
        if poll_timeout <= 0:
            raise ValueError("poll_timeout must be greater than zero")

        query = self.create_query(filters)
        deadline = self._monotonic() + poll_timeout
        while query.status not in TERMINAL_QUERY_STATUSES:
            remaining = deadline - self._monotonic()
            if remaining <= 0:
                return AuditCollectionResult(
                    query=query,
                    records=(),
                    complete=False,
                    errors=(f"Audit query polling timed out while status was {query.status}",),
                )
            self._poll_sleep(min(poll_interval, remaining))
            try:
                query = self.get_query(query.id)
            except (FabricApiError, TypeError, ValueError) as error:
                return AuditCollectionResult(
                    query=query,
                    records=(),
                    complete=False,
                    errors=(f"Audit query status polling failed: {error}",),
                )

        if query.status != "succeeded":
            return AuditCollectionResult(
                query=query,
                records=(),
                complete=False,
                errors=(f"Audit query completed with status {query.status}",),
            )

        records: list[AuditLogRecord] = []
        try:
            records.extend(self.iter_records(query.id))
        except (FabricApiError, TypeError, ValueError) as error:
            return AuditCollectionResult(
                query=query,
                records=tuple(records),
                complete=False,
                errors=(f"Audit record collection failed: {error}",),
            )
        return AuditCollectionResult(
            query=query,
            records=tuple(records),
            complete=True,
        )
