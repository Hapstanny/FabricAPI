"""Typed, resilient clients for the Microsoft Fabric and Power BI REST APIs."""

from .auth import credential_from_environment
from .client import FabricClient, PowerBIClient, RestApiError

__all__ = ["FabricClient", "PowerBIClient", "RestApiError", "credential_from_environment"]
