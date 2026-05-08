"""Sanitized excerpt from SmartHire proprietary codebase.

Demonstrates the Headless Service Layer pattern (ADR-0032):
- Handlers (aiogram / FastAPI) call services, never repositories directly.
- Services accept `tenant_id` explicitly — no contextvar magic inside domain logic.
- Same service method works from a Telegram handler, REST endpoint, cron job, or unit test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from core.domain.errors import AnketaNotFoundError, TenantPermissionError
from core.repositories.interfaces import AnketaRepository, AuditLogRepository


# ---------------------------------------------------------------------------
# Domain value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AnketaCreateCommand:
    """Command object for creating a new anketa.

    Args:
        tenant_id: Owning tenant UUID (always explicit, never inferred).
        title: Human-readable anketa title.
        fields: Ordered list of field definitions (JSON-serialisable).
        created_by: User UUID who initiated the action.
    """

    tenant_id: UUID
    title: str
    fields: list[dict[str, object]]
    created_by: UUID


@dataclass(frozen=True, slots=True)
class AnketaDTO:
    """Read model returned by service methods.

    Args:
        id: Anketa UUID.
        tenant_id: Owning tenant UUID.
        title: Anketa title.
        fields: Field definitions.
        created_at: Creation timestamp (UTC).
        is_active: Whether the anketa is published.
    """

    id: UUID
    tenant_id: UUID
    title: str
    fields: list[dict[str, object]]
    created_at: datetime
    is_active: bool


# ---------------------------------------------------------------------------
# Service — the only layer handlers are allowed to call
# ---------------------------------------------------------------------------


class AnketaService:
    """Business operations on Anketa aggregate.

    Handlers (aiogram / FastAPI) depend on this class via DI container.
    The service never imports from `core/database/` or `core/repositories/`
    directly — it receives repository interfaces through constructor injection.

    Args:
        repo: Anketa repository (async, tenant-aware).
        audit_repo: Audit log repository for write operations.
    """

    def __init__(
        self,
        repo: AnketaRepository,
        audit_repo: AuditLogRepository,
    ) -> None:
        self._repo = repo
        self._audit = audit_repo

    async def create(self, cmd: AnketaCreateCommand) -> AnketaDTO:
        """Create and persist a new anketa.

        Args:
            cmd: Validated command with all required fields.

        Returns:
            Newly created anketa DTO.

        Raises:
            TenantPermissionError: If tenant has exceeded anketa quota.
        """
        quota = await self._repo.count_active(tenant_id=cmd.tenant_id)
        if quota >= 50:
            raise TenantPermissionError(
                f"Tenant {cmd.tenant_id} reached anketa limit (50)"
            )

        anketa_id = uuid4()
        now = datetime.now(UTC)

        await self._repo.insert(
            id=anketa_id,
            tenant_id=cmd.tenant_id,
            title=cmd.title,
            fields=cmd.fields,
            created_at=now,
            created_by=cmd.created_by,
        )
        await self._audit.log(
            tenant_id=cmd.tenant_id,
            actor_id=cmd.created_by,
            action="anketa.created",
            resource_id=anketa_id,
        )

        return AnketaDTO(
            id=anketa_id,
            tenant_id=cmd.tenant_id,
            title=cmd.title,
            fields=cmd.fields,
            created_at=now,
            is_active=False,
        )

    async def get(self, tenant_id: UUID, anketa_id: UUID) -> AnketaDTO:
        """Fetch a single anketa, enforcing tenant ownership.

        Args:
            tenant_id: Caller's tenant UUID.
            anketa_id: Target anketa UUID.

        Returns:
            Anketa DTO.

        Raises:
            AnketaNotFoundError: If anketa does not exist or belongs to another tenant.
        """
        row = await self._repo.get_by_id(anketa_id=anketa_id, tenant_id=tenant_id)
        if row is None:
            raise AnketaNotFoundError(anketa_id)

        return AnketaDTO(
            id=row.id,
            tenant_id=row.tenant_id,
            title=row.title,
            fields=row.fields,
            created_at=row.created_at,
            is_active=row.is_active,
        )
