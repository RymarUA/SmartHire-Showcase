"""Sanitized excerpt from SmartHire proprietary codebase.

Demonstrates the Module Federation pattern (ADR-005):
- BaseModule ABC defines the 4-method contract all business modules must satisfy.
- ModuleRegistry discovers, wires, and health-aggregates all registered modules.
- No module imports another module — events flow through Redis pub/sub.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter

    from core.container import Container


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class ModuleStatus(str, Enum):
    """Health status of a single module.

    Args:
        HEALTHY: All module dependencies are reachable.
        DEGRADED: Module is operational but with reduced functionality.
        UNAVAILABLE: Module cannot serve requests.
    """

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class CatalogItem:
    """Represents a single entry in a tenant's bot main menu.

    Args:
        key: Unique identifier used in callback_data (e.g. 'booking').
        label: Localised button text shown to the user.
        emoji: Optional emoji prefix for the button.
        order: Sort order in the menu (lower = higher).
    """

    key: str
    label: str
    emoji: str = ""
    order: int = 100


@dataclass(slots=True)
class ModuleHealth:
    """Health report returned by a module.

    Args:
        module_name: Human-readable name (e.g. 'BookingModule').
        status: Overall module status.
        details: Optional key-value diagnostic info (latencies, queue depth…).
    """

    module_name: str
    status: ModuleStatus
    details: dict[str, object] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# BaseModule ABC — the only contract modules must satisfy
# ---------------------------------------------------------------------------


class BaseModule(ABC):
    """Abstract base for all SmartHire business modules.

    Every module registered in `ModuleRegistry` must inherit from this class
    and implement all four abstract methods.

    Convention:
        - `setup` is called once at application startup, before any request.
        - `get_catalog_items` is called per-request for menu rendering.
        - `get_routes` is called once at startup to mount API routes.
        - `get_health` is called by the `/health/ready` endpoint.
    """

    @abstractmethod
    async def setup(self, container: Container) -> None:
        """Initialise module dependencies from the DI container.

        Args:
            container: Application-level dependency-injector Container.
        """

    @abstractmethod
    def get_catalog_items(self, tenant_id: str) -> list[CatalogItem]:
        """Return menu items to show for this tenant.

        Items may differ per tenant based on their module config.

        Args:
            tenant_id: The tenant requesting the catalog.

        Returns:
            Ordered list of catalog items (may be empty if module is disabled
            for this tenant).
        """

    @abstractmethod
    def get_routes(self) -> list[APIRouter]:
        """Return FastAPI routers to mount at application startup.

        Returns:
            List of APIRouter instances (empty list if module has no API).
        """

    @abstractmethod
    async def get_health(self) -> ModuleHealth:
        """Check and return current module health.

        Returns:
            ModuleHealth dataclass with status and optional diagnostic details.
        """


# ---------------------------------------------------------------------------
# ModuleRegistry — discovers and wires modules at startup
# ---------------------------------------------------------------------------


class ModuleRegistry:
    """Registry that manages all active BaseModule instances.

    Modules are registered at startup. The registry:
    - Calls `setup()` on each module in registration order.
    - Aggregates `get_routes()` for FastAPI router mounting.
    - Aggregates `get_health()` for the `/health/ready` K8s probe.

    Args:
        container: DI container passed to each module's `setup()`.
    """

    def __init__(self, container: Container) -> None:
        self._container = container
        self._modules: list[BaseModule] = []

    def register(self, module: BaseModule) -> None:
        """Add a module to the registry.

        Args:
            module: Concrete BaseModule instance to register.
        """
        self._modules.append(module)

    async def setup_all(self) -> None:
        """Initialise all registered modules sequentially.

        Called once during application startup, after the DI container
        is fully wired.
        """
        for module in self._modules:
            await module.setup(self._container)

    def all_routes(self) -> list[APIRouter]:
        """Collect APIRouters from all modules for FastAPI mounting.

        Returns:
            Flat list of all routers across all modules.
        """
        routes: list[APIRouter] = []
        for module in self._modules:
            routes.extend(module.get_routes())
        return routes

    async def aggregate_health(self) -> list[ModuleHealth]:
        """Run health checks on all modules concurrently.

        Returns:
            Health report for every registered module.
        """
        import asyncio

        return list(
            await asyncio.gather(
                *(m.get_health() for m in self._modules),
                return_exceptions=False,
            )
        )

    def catalog_for_tenant(self, tenant_id: str) -> list[CatalogItem]:
        """Aggregate menu items across all modules for a given tenant.

        Items are sorted by `CatalogItem.order` ascending.

        Args:
            tenant_id: Target tenant UUID string.

        Returns:
            Merged, sorted catalog item list.
        """
        items: list[CatalogItem] = []
        for module in self._modules:
            items.extend(module.get_catalog_items(tenant_id))
        return sorted(items, key=lambda i: i.order)
