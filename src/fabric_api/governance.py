"""Purview audit export and governance analysis."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import AuditCollectionResult, AuditLogRecord

CSV_FIELDS: Mapping[str, tuple[str, ...]] = {
    "audit-records": (
        "id",
        "createdDateTime",
        "day",
        "recordType",
        "operation",
        "activity",
        "service",
        "userPrincipalName",
        "userId",
        "objectId",
        "clientIp",
        "appHost",
        "appIdentity",
        "promptMessageCount",
        "responseMessageCount",
        "unknownMessageCount",
        "accessedResourceCount",
        "sensitivityLabelIds",
        "auditData",
    ),
    "copilot-daily": ("day", "activeUsers", "interactionCount"),
    "copilot-dimensions": ("dimension", "value", "count"),
    "copilot-messages": (
        "day",
        "user",
        "appHost",
        "interactionCount",
        "promptMessageCount",
        "responseMessageCount",
        "unknownMessageCount",
    ),
    "copilot-resources": (
        "source",
        "resourceId",
        "resourceType",
        "resourceName",
        "siteUrl",
        "sensitivityLabelId",
        "action",
        "count",
    ),
    "powerbi-fabric-trends": (
        "day",
        "service",
        "operation",
        "activity",
        "user",
        "objectId",
        "count",
    ),
}


def analyze_audit_records(records: Sequence[AuditLogRecord]) -> dict[str, list[dict[str, Any]]]:
    """Create privacy-aware usage counts without claiming prompt text is available."""
    flattened = [_flatten_record(record) for record in records]
    copilot = [record for record in records if _is_copilot_record(record)]
    power_bi_fabric = [record for record in records if _is_power_bi_or_fabric_record(record)]

    daily_users: dict[str, set[str]] = {}
    daily_interactions: Counter[str] = Counter()
    dimensions: Counter[tuple[str, str]] = Counter()
    messages: Counter[tuple[str, str, str]] = Counter()
    message_details: dict[tuple[str, str, str], Counter[str]] = {}
    resources: Counter[tuple[str, str, str, str, str, str, str]] = Counter()

    for record in copilot:
        audit_data = record.audit_data
        event_data = _mapping(_get(audit_data, "CopilotEventData", "copilotEventData"))
        day = _day(record.created_date_time)
        user = _record_user(record)
        service = _record_service(record)
        operation = _record_operation(record)
        app_host = _text(_get(event_data, "AppHost", "appHost"))
        app_identity = _text(_get(audit_data, "AppIdentity", "appIdentity"))
        daily_interactions[day] += 1
        if user:
            daily_users.setdefault(day, set()).add(user)
        for dimension, value in (
            ("user", user),
            ("service", service),
            ("operation", operation),
            ("appHost", app_host),
            ("appIdentity", app_identity),
        ):
            dimensions[(dimension, value or "(unknown)")] += 1

        message_key = (day, user or "(unknown)", app_host or "(unknown)")
        messages[message_key] += 1
        detail = message_details.setdefault(message_key, Counter())
        for message in _mapping_items(_get(event_data, "Messages", "messages")):
            is_prompt = _get(message, "isPrompt", "IsPrompt")
            if is_prompt is True:
                detail["promptMessageCount"] += 1
            elif is_prompt is False:
                detail["responseMessageCount"] += 1
            else:
                detail["unknownMessageCount"] += 1

        for source, values in (
            (
                "accessedResource",
                _mapping_items(_get(event_data, "AccessedResources", "accessedResources")),
            ),
            ("context", _mapping_items(_get(event_data, "Contexts", "contexts"))),
        ):
            for resource in values:
                key = (
                    source,
                    _text(_get(resource, "Id", "id")),
                    _text(_get(resource, "Type", "type")),
                    _text(_get(resource, "Name", "name")),
                    _text(_get(resource, "SiteUrl", "siteUrl")),
                    _text(_get(resource, "SensitivityLabelId", "sensitivityLabelId")),
                    _text(_get(resource, "Action", "action")),
                )
                resources[key] += 1

    trends: Counter[tuple[str, str, str, str, str, str]] = Counter()
    for record in power_bi_fabric:
        trends[
            (
                _day(record.created_date_time),
                _record_service(record),
                _record_operation(record),
                _text(_get(record.audit_data, "Activity", "activity")),
                _record_user(record),
                record.object_id or _text(_get(record.audit_data, "ObjectId", "objectId")),
            )
        ] += 1

    return {
        "audit-records": flattened,
        "copilot-daily": [
            {
                "day": day,
                "activeUsers": len(daily_users.get(day, set())),
                "interactionCount": count,
            }
            for day, count in sorted(daily_interactions.items())
        ],
        "copilot-dimensions": [
            {"dimension": dimension, "value": value, "count": count}
            for (dimension, value), count in sorted(dimensions.items())
        ],
        "copilot-messages": [
            {
                "day": key[0],
                "user": key[1],
                "appHost": key[2],
                "interactionCount": interaction_count,
                "promptMessageCount": message_details[key]["promptMessageCount"],
                "responseMessageCount": message_details[key]["responseMessageCount"],
                "unknownMessageCount": message_details[key]["unknownMessageCount"],
            }
            for key, interaction_count in sorted(messages.items())
        ],
        "copilot-resources": [
            {
                "source": key[0],
                "resourceId": key[1],
                "resourceType": key[2],
                "resourceName": key[3],
                "siteUrl": key[4],
                "sensitivityLabelId": key[5],
                "action": key[6],
                "count": count,
            }
            for key, count in sorted(resources.items())
        ],
        "powerbi-fabric-trends": [
            {
                "day": key[0],
                "service": key[1],
                "operation": key[2],
                "activity": key[3],
                "user": key[4],
                "objectId": key[5],
                "count": count,
            }
            for key, count in sorted(trends.items())
        ],
    }


def export_audit_collection(
    result: AuditCollectionResult,
    output_directory: Path,
) -> dict[str, Any]:
    """Write raw records and flattened governance summaries."""
    output_directory.mkdir(parents=True, exist_ok=True)
    raw_records = [dict(record.raw) for record in result.records]
    analyses = analyze_audit_records(result.records)
    generated_at = datetime.now(timezone.utc).isoformat()

    raw_json_path = output_directory / "audit-records.json"
    raw_jsonl_path = output_directory / "audit-records.jsonl"
    manifest_path = output_directory / "manifest.json"
    raw_json_path.write_text(
        json.dumps(
            {
                "generatedAtUtc": generated_at,
                "complete": result.complete,
                "errors": list(result.errors),
                "query": dict(result.query.raw),
                "records": raw_records,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    raw_jsonl_path.write_text(
        "".join(json.dumps(record, default=str) + "\n" for record in raw_records),
        encoding="utf-8",
    )

    files = [raw_json_path.name, raw_jsonl_path.name]
    for name, rows in analyses.items():
        path = output_directory / f"{name}.csv"
        _write_csv(path, rows, CSV_FIELDS[name])
        files.append(path.name)

    manifest: dict[str, Any] = {
        "generatedAtUtc": generated_at,
        "outputDirectory": str(output_directory),
        "queryId": result.query.id,
        "queryStatus": result.query.status,
        "complete": result.complete,
        "recordCount": len(result.records),
        "errors": list(result.errors),
        "files": [manifest_path.name, *files],
        "notes": [
            "Message counts use CopilotEventData.Messages/isPrompt when present.",
            "Audit records do not necessarily contain prompt or response text.",
            "Usage counts alone do not establish productivity impact.",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _write_csv(
    path: Path,
    rows: Iterable[Mapping[str, Any]],
    fieldnames: Sequence[str],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(
            {field: _safe_csv_value(value) for field, value in row.items()} for row in rows
        )


def _safe_csv_value(value: object) -> object:
    if not isinstance(value, str):
        return value
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _flatten_record(record: AuditLogRecord) -> dict[str, Any]:
    event_data = _mapping(_get(record.audit_data, "CopilotEventData", "copilotEventData"))
    messages = _mapping_items(_get(event_data, "Messages", "messages"))
    resources = _mapping_items(_get(event_data, "AccessedResources", "accessedResources"))
    prompts = sum(_get(message, "isPrompt", "IsPrompt") is True for message in messages)
    responses = sum(_get(message, "isPrompt", "IsPrompt") is False for message in messages)
    labels = sorted(
        {
            _text(_get(resource, "SensitivityLabelId", "sensitivityLabelId"))
            for resource in resources
            if _text(_get(resource, "SensitivityLabelId", "sensitivityLabelId"))
        }
    )
    return {
        "id": record.id,
        "createdDateTime": record.created_date_time or "",
        "day": _day(record.created_date_time),
        "recordType": record.record_type or "",
        "operation": _record_operation(record),
        "activity": _text(_get(record.audit_data, "Activity", "activity")),
        "service": _record_service(record),
        "userPrincipalName": record.user_principal_name or "",
        "userId": record.user_id or "",
        "objectId": record.object_id or "",
        "clientIp": record.client_ip or "",
        "appHost": _text(_get(event_data, "AppHost", "appHost")),
        "appIdentity": _text(_get(record.audit_data, "AppIdentity", "appIdentity")),
        "promptMessageCount": prompts,
        "responseMessageCount": responses,
        "unknownMessageCount": len(messages) - prompts - responses,
        "accessedResourceCount": len(resources),
        "sensitivityLabelIds": ";".join(labels),
        "auditData": json.dumps(record.audit_data, separators=(",", ":"), default=str),
    }


def _is_copilot_record(record: AuditLogRecord) -> bool:
    return _record_operation(record).lower() == "copilotinteraction"


def _is_power_bi_or_fabric_record(record: AuditLogRecord) -> bool:
    if (record.record_type or "").lower() == "powerbiaudit":
        return True
    service = _record_service(record).lower().replace(" ", "")
    return service in {"powerbi", "fabric", "microsoftfabric"}


def _record_user(record: AuditLogRecord) -> str:
    return record.user_principal_name or _text(
        _get(record.audit_data, "UserId", "userId", "UserPrincipalName")
    )


def _record_service(record: AuditLogRecord) -> str:
    return record.service or _text(_get(record.audit_data, "Workload", "workload", "Service"))


def _record_operation(record: AuditLogRecord) -> str:
    return record.operation or _text(_get(record.audit_data, "Operation", "operation"))


def _day(value: str | None) -> str:
    return value[:10] if value else "(unknown)"


def _get(value: Mapping[str, Any], *keys: str) -> object:
    for key in keys:
        if key in value:
            return value[key]
    return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_items(value: object) -> list[Mapping[str, Any]]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _text(value: object) -> str:
    return str(value) if value is not None else ""
