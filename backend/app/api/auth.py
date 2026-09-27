"""Authentication and RBAC for GeoSamanvay API.

Auth model:
  - GS_DEMO_MODE=1 (default): open access, all roles granted — for SIH demo
  - GS_API_KEY set: X-API-Key header required on protected routes
  - Per-route role requirements enforced via require_role() dependency

Roles (from domain model):
  ADMIN         full access including user/key management
  DATA_OPERATOR ingest datasets, add provenance nodes
  ANALYST       read-only + run harmonization
  REVIEWER      approve/reject proposals in review queue
  APPROVER      approve + override auto-decisions
  AUDITOR       read-only access to audit trails and evidence
"""
from __future__ import annotations
import hmac
import os
from typing import Optional

from fastapi import Request, HTTPException, status, Header, Depends


DEMO_MODE: bool = os.environ.get("GS_DEMO_MODE", "1") == "1"
_API_KEY: str = os.environ.get("GS_API_KEY", "")

PUBLIC_PATHS = {
    "/api/v1/health", "/api/v1/formats",
    "/docs", "/openapi.json", "/redoc", "/",
    "/favicon.ico",
}

# Route-level role requirements (path prefix → minimum role set)
# If DEMO_MODE, all role checks pass automatically.
_ROUTE_ROLES: dict[str, set[str]] = {
    "/api/v1/cases":                     {"ADMIN", "DATA_OPERATOR", "ANALYST", "REVIEWER", "APPROVER", "AUDITOR"},
    "/api/v1/cases/{id}/datasets":       {"ADMIN", "DATA_OPERATOR"},
    "/api/v1/cases/{id}/harmonize":      {"ADMIN", "DATA_OPERATOR", "ANALYST"},
    "/api/v1/cases/{id}/proposals":      {"REVIEWER", "APPROVER", "ADMIN"},
    "/api/v1/cases/{id}/review":         {"REVIEWER", "APPROVER", "ADMIN"},
    "/api/v1/cases/{id}/audit":          {"AUDITOR", "ADMIN"},
    "/api/v1/verify":                    {"AUDITOR", "ANALYST", "ADMIN"},
}


def _is_public(path: str) -> bool:
    return path in PUBLIC_PATHS or path.startswith(("/static", "/assets"))


async def require_api_key(request: Request) -> Optional[str]:
    """Middleware: validate API key on non-public routes."""
    if DEMO_MODE or not _API_KEY:
        return None
    if _is_public(request.url.path):
        return None
    key = request.headers.get("X-API-Key", "")
    if not key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if not hmac.compare_digest(key.encode(), _API_KEY.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return key


def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory: enforce that the caller has one of the
    allowed roles.

    In DEMO_MODE all role checks pass. In production the role is extracted
    from the X-GS-Role header (in a real deployment this would come from
    a JWT claim instead).
    """
    async def _check(
        request: Request,
        x_gs_role: Optional[str] = Header(default=None, alias="X-GS-Role"),
    ):
        if DEMO_MODE:
            return "ADMIN"  # demo mode grants all roles

        role = (x_gs_role or "ANALYST").upper()
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role {role!r} is not permitted for this action. "
                    f"Required: one of {sorted(allowed_roles)}"
                ),
            )
        return role

    return _check


# Convenience role dependencies
require_data_operator = require_role("ADMIN", "DATA_OPERATOR")
require_analyst       = require_role("ADMIN", "DATA_OPERATOR", "ANALYST")
require_reviewer      = require_role("ADMIN", "REVIEWER", "APPROVER")
require_approver      = require_role("ADMIN", "APPROVER")
require_auditor       = require_role("ADMIN", "AUDITOR", "ANALYST", "REVIEWER", "APPROVER")
require_admin         = require_role("ADMIN")
