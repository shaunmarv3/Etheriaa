"""audit_log writes (spec 11.2): who did what, never health content."""

from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from etheria.db.models import AuditLog


async def record(
    session: AsyncSession,
    action: str,
    *,
    user_ref: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    await session.execute(
        insert(AuditLog).values(
            action=action,
            user_ref=user_ref,
            ip=ip,
            user_agent=user_agent,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
        )
    )
