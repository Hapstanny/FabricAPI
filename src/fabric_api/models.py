"""Response models shared by the clients."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


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
            continuation_uri=_optional_string(payload.get("continuationUri")),
            raw=payload,
        )


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None
