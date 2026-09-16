"""Response models shared by the clients."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class FabricItem:
    id: str
    display_name: str
    type: str
    workspace_id: str | None = None
    description: str | None = None
    folder_id: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> FabricItem:
        return cls(
            id=str(value["id"]),
            display_name=str(value.get("displayName", "")),
            type=str(value.get("type", "")),
            workspace_id=_optional_string(value.get("workspaceId")),
            description=_optional_string(value.get("description")),
            folder_id=_optional_string(value.get("folderId")),
            raw=value,
        )


@dataclass(frozen=True, slots=True)
class Page:
    value: tuple[Mapping[str, Any], ...]
    continuation_token: str | None = None
    continuation_uri: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
        *,
        value_key: str = "value",
    ) -> Page:
        values = payload.get(value_key, [])
        if not isinstance(values, list):
            raise TypeError(f"Expected '{value_key}' to be a list")
        return cls(
            value=tuple(item for item in values if isinstance(item, Mapping)),
            continuation_token=_optional_string(payload.get("continuationToken")),
            continuation_uri=_optional_string(
                payload.get("continuationUri") or payload.get("@odata.nextLink")
            ),
            raw=payload,
        )


AuditLogQueryStatus = Literal[
    "notStarted",
    "running",
    "succeeded",
    "failed",
    "cancelled",
    "unknownFutureValue",
]


@dataclass(frozen=True, slots=True)
class AuditLogQueryFilters:
    """Documented Microsoft Graph Purview Audit Search filters."""

    filter_start: datetime
    filter_end: datetime
    display_name: str | None = None
    record_type_filters: tuple[str, ...] = ()
    service_filter: str | None = None
    operation_filters: tuple[str, ...] = ()
    user_principal_name_filters: tuple[str, ...] = ()
    ip_address_filters: tuple[str, ...] = ()
    object_id_filters: tuple[str, ...] = ()
    keyword_filter: str | None = None

    def __post_init__(self) -> None:
        start = _as_utc(self.filter_start)
        end = _as_utc(self.filter_end)
        if end <= start:
            raise ValueError("filter_end must be later than filter_start")

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "filterStartDateTime": _format_graph_datetime(_as_utc(self.filter_start)),
            "filterEndDateTime": _format_graph_datetime(_as_utc(self.filter_end)),
        }
        optional_scalars = {
            "displayName": self.display_name,
            "serviceFilter": self.service_filter,
            "keywordFilter": self.keyword_filter,
        }
        payload.update({key: value for key, value in optional_scalars.items() if value})
        optional_collections = {
            "recordTypeFilters": self.record_type_filters,
            "operationFilters": self.operation_filters,
            "userPrincipalNameFilters": self.user_principal_name_filters,
            "ipAddressFilters": self.ip_address_filters,
            "objectIdFilters": self.object_id_filters,
        }
        payload.update({key: list(value) for key, value in optional_collections.items() if value})
        return payload


@dataclass(frozen=True, slots=True)
class AuditLogQuery:
    id: str
    status: AuditLogQueryStatus
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AuditLogQuery:
        raw_status = str(value.get("status", "unknownFutureValue"))
        statuses = {
            "notStarted",
            "running",
            "succeeded",
            "failed",
            "cancelled",
            "unknownFutureValue",
        }
        status = raw_status if raw_status in statuses else "unknownFutureValue"
        return cls(
            id=str(value["id"]),
            status=status,  # type: ignore[arg-type]
            raw=value,
        )


@dataclass(frozen=True, slots=True)
class AuditLogRecord:
    id: str
    created_date_time: str | None
    record_type: str | None
    operation: str | None
    service: str | None
    user_principal_name: str | None
    user_id: str | None
    object_id: str | None
    client_ip: str | None
    audit_data: Mapping[str, Any]
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AuditLogRecord:
        audit_data = _mapping_or_json(value.get("auditData"))
        return cls(
            id=str(value.get("id", audit_data.get("Id", ""))),
            created_date_time=_optional_string(
                value.get("createdDateTime", audit_data.get("CreationTime"))
            ),
            record_type=_optional_string(
                value.get("auditLogRecordType", audit_data.get("RecordType"))
            ),
            operation=_optional_string(value.get("operation", audit_data.get("Operation"))),
            service=_optional_string(value.get("service", audit_data.get("Workload"))),
            user_principal_name=_optional_string(
                value.get("userPrincipalName", audit_data.get("UserId"))
            ),
            user_id=_optional_string(value.get("userId", audit_data.get("UserKey"))),
            object_id=_optional_string(value.get("objectId", audit_data.get("ObjectId"))),
            client_ip=_optional_string(value.get("clientIp", audit_data.get("ClientIP"))),
            audit_data=audit_data,
            raw=value,
        )


@dataclass(frozen=True, slots=True)
class AuditCollectionResult:
    query: AuditLogQuery
    records: tuple[AuditLogRecord, ...]
    complete: bool
    errors: tuple[str, ...] = ()


def _mapping_or_json(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, Mapping):
            return parsed
    return {}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("audit query timestamps must include a UTC offset")
    return value.astimezone(timezone.utc)


def _format_graph_datetime(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None
