# ADR 0032: Service Layer Enforcement

**Status:** Completed
**Date:** 2026-05-02
**Author:** SmartHire Architecture Team

## Context

Following the headless architecture transition, the `handlers/` directory still contained direct references to repositories and gateways. This violated the "Strict Service Layer" principle where UI logic (handlers) should only interact with the Service Layer.

Issues identified:
- Handlers directly importing `core.repositories`.
- Raw SQL queries embedded in admin handlers.
- Complex orchestration logic (e.g., payment creation + outbox) living in handlers.
- Redundant repository access logic across multiple files.

## Decision

Enforce strict separation between handlers and data access layers:

1. **Expand Service Layer**: Adding high-level methods to `AnketaService`, `PaymentService`, and `DatabaseService` to encapsulate all DB operations.
2. **Create `OutboxService`**: Decoupling background message logic from handlers.
3. **DI Injection**: All services accessible via Dependency Injection container.
4. **Refactor Handlers**: Systematically updating all files in `handlers/` to use service method calls exclusively.
5. **Remove Repository Imports**: Deleting all `from core.repositories import ...` lines from handlers.

## Consequences

- **100% Headless Architecture**: UI transports fully decoupled from persistence layer.
- **Improved Maintainability**: Business logic centralized in services.
- **Better Security**: Tenancy isolation and SQL safety managed at service level.
- **Reduced Circular Dependencies**: Lazy loading resolves import loops.
- **Architectural Integrity**: Verified via semgrep rule.

## Implementation Summary

| Component | Status | Details |
|-----------|--------|---------|
| `AnketaService` | ✅ Expanded | Added `hard_delete_anketa`, `get_active_anketa_ids_for_sync`, etc. |
| `PaymentService` | ✅ Expanded | Added `get_revenue`, `get_pending_payments`, `get_all_raw`. |
| `DatabaseService` | ✅ Expanded | Added `ping_db`, `execute_raw_sql`, `fetch_raw_sql`, etc. |
| `OutboxService` | ✅ Created | New service for OutboxRepository operations. |
| Admin Handlers | ✅ Refactored | 31+ files updated |
| Semgrep Verification | ✅ Passed | 0 violations |

## Key Pattern

```python
# BAD: Handler directly accessing repository
from core.repositories.anketa import AnketaGateway
gateway = AnketaGateway(session)
ankety = await gateway.get_all(tenant_id)

# GOOD: Handler using Service Layer
from core.services.anketa import AnketaService
ankety = await anketa_service.get_all(tenant_id)
```

## References

- Service layer: `core/services/`
- DI Container: `core/container.py`
- Semgrep rules: `.semgrep/smarthire.yml`
