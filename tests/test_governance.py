from __future__ import annotations

import csv
import json
from pathlib import Path

from fabric_api.governance import analyze_audit_records, export_audit_collection
from fabric_api.models import AuditCollectionResult, AuditLogQuery, AuditLogRecord


def _records() -> tuple[AuditLogRecord, ...]:
    return (
        AuditLogRecord.from_dict(
            {
                "id": "copilot-1",
                "createdDateTime": "2026-09-01T10:00:00Z",
                "auditLogRecordType": "powerBIAudit",
                "operation": "CopilotInteraction",
                "service": "PowerBI",
                "userPrincipalName": "analyst@example.com",
                "objectId": "report-1",
                "auditData": {
                    "Activity": "CopilotInteraction",
                    "AppIdentity": "Copilot.Fabric.CopilotforPowerBI",
                    "CopilotEventData": {
                        "AppHost": "Power BI",
                        "Messages": [
                            {"Id": "prompt-1", "isPrompt": True},
                            {"Id": "response-1", "isPrompt": False},
                        ],
                        "Contexts": [{"Id": "report-1", "Type": "Report"}],
                        "AccessedResources": [
                            {
                                "Id": "model-1",
                                "Type": "SemanticModel",
                                "SensitivityLabelId": "label-1",
                                "Action": "Read",
                            }
                        ],
                    },
                },
            }
        ),
        AuditLogRecord.from_dict(
            {
                "id": "powerbi-2",
                "createdDateTime": "2026-09-01T11:00:00Z",
                "auditLogRecordType": "powerBIAudit",
                "operation": "ViewReport",
                "service": "PowerBI",
                "userPrincipalName": "viewer@example.com",
                "objectId": "report-1",
                "auditData": {"Activity": "ViewReport"},
            }
        ),
    )


def test_governance_analysis_counts_copilot_and_power_bi_dimensions() -> None:
    analysis = analyze_audit_records(_records())

    assert analysis["copilot-daily"] == [
        {"day": "2026-09-01", "activeUsers": 1, "interactionCount": 1}
    ]
    assert analysis["copilot-messages"][0]["promptMessageCount"] == 1
    assert analysis["copilot-messages"][0]["responseMessageCount"] == 1
    assert {
        "dimension": "appIdentity",
        "value": "Copilot.Fabric.CopilotforPowerBI",
        "count": 1,
    } in analysis["copilot-dimensions"]
    assert any(row["sensitivityLabelId"] == "label-1" for row in analysis["copilot-resources"])
    assert sum(row["count"] for row in analysis["powerbi-fabric-trends"]) == 2
    assert analysis["audit-records"][0]["auditData"]


def test_export_retains_raw_records_and_writes_all_summaries(tmp_path: Path) -> None:
    result = AuditCollectionResult(
        query=AuditLogQuery(
            id="query-1",
            status="succeeded",
            raw={"id": "query-1", "status": "succeeded"},
        ),
        records=_records(),
        complete=False,
        errors=("A later page failed",),
    )

    manifest = export_audit_collection(result, tmp_path)

    assert manifest["complete"] is False
    assert manifest["recordCount"] == 2
    raw = json.loads((tmp_path / "audit-records.json").read_text(encoding="utf-8"))
    assert raw["records"][0]["auditData"]["CopilotEventData"]["AppHost"] == "Power BI"
    assert raw["errors"] == ["A later page failed"]
    assert len((tmp_path / "audit-records.jsonl").read_text(encoding="utf-8").splitlines()) == 2
    with (tmp_path / "audit-records.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["promptMessageCount"] == "1"
    assert rows[0]["appIdentity"] == "Copilot.Fabric.CopilotforPowerBI"
    assert set(manifest["files"]) >= {
        "manifest.json",
        "copilot-daily.csv",
        "copilot-dimensions.csv",
        "copilot-messages.csv",
        "copilot-resources.csv",
        "powerbi-fabric-trends.csv",
    }
