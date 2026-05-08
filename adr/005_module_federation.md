# ADR-005: Module Federation

**Status:** Accepted  
**Date:** 2024-09-12  
**Last reviewed:** 2026-04-19

## Context

SmartHire serves B2B tenants across vastly different industries: recruiting agencies, rental services,
service shops, e-commerce. Each vertical requires different bot menus, API routes, and business logic.
We needed a way to ship new verticals without touching platform core and without coupling modules
to each other.

## Decision

Introduce a `BaseModule` ABC with a 4-method contract. A `ModuleRegistry` discovers and wires
modules at startup. Inter-module communication happens exclusively via Redis pub/sub — no direct
imports between modules.

```python
class BaseModule(ABC):
    @abstractmethod
    async def setup(self, container: Container) -> None: ...

    @abstractmethod
    def get_catalog_items(self, tenant_id: str) -> list[CatalogItem]: ...

    @abstractmethod
    def get_routes(self) -> list[APIRouter]: ...

    @abstractmethod
    async def get_health(self) -> ModuleHealth: ...
```

Per-tenant activation is stored in `module_config` DB table. Dashboard toggles it instantly,
no release required.

## Consequences

### Positive
- New business vertical: implement `BaseModule`, register in `pyproject.toml` entry points → done in 1–2 days.
- Tenants A and B can run completely different module sets in the same process.
- Modules are independently testable: no Telegram bot required in unit tests.
- `ModuleRegistry.health()` aggregates all module health into one K8s readiness endpoint.

### Negative
- Redis pub/sub adds latency for cross-module events (~1ms).
- Module developers must learn the `BaseModule` contract.
- Dynamic activation requires DB round-trip on bot startup per tenant.

## Implementation

- `core/modules/base.py` — `BaseModule` ABC, `CatalogItem`, `ModuleHealth` types.
- `core/modules/registry.py` — `ModuleRegistry` with lazy loading and health aggregation.
- `core/modules/*/` — 7 concrete modules (catalog, booking, shop, billing, recruiting, support, shop_variant).

## References

- `code/base_module.py` — sanitized excerpt of `BaseModule` ABC.
- ADR-001: Multi-Tenant Architecture (per-tenant module activation depends on tenant_id isolation).
