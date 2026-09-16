"""Typed clients for Microsoft Fabric, Power BI, and Purview Audit APIs."""

from .auth import TokenCredentialFactory
from .client import FabricClient, PowerBIClient
from .errors import (
    ApiError,
    AuthenticationConfigurationError,
    FabricApiError,
    UnsafeRequestUrlError,
)
from .governance import analyze_audit_records, export_audit_collection
from .models import AuditCollectionResult, AuditLogQueryFilters, AuditLogRecord
from .purview import PurviewAuditClient

__all__ = [
    "AuditCollectionResult",
    "AuditLogQueryFilters",
    "AuditLogRecord",
    "ApiError",
    "AuthenticationConfigurationError",
    "FabricApiError",
    "FabricClient",
    "PowerBIClient",
    "PurviewAuditClient",
    "TokenCredentialFactory",
    "UnsafeRequestUrlError",
    "analyze_audit_records",
    "export_audit_collection",
]
