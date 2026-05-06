# Module Federation Architecture

SmartHire uses a pluggable module system that allows adding new business directions (catalog, booking, shop, billing, recruiting, support) in **1-2 days** without modifying the core.

## Core Concept

```
┌─────────────────────────────────────────────────────────────┐
│                    ModuleRegistry                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Catalog  │  │ Booking  │  │  Shop    │  │ Recruiting│   │
│  │ Module   │  │ Module   │  │ Module   │  │ Module    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## BaseModule Contract

Every module inherits from `BaseModule` and implements:

```python
from core.modules.base_module import BaseModule

class CatalogModule(BaseModule):
    @property
    def module_id(self) -> str:
        return "catalog"

    @property
    def display_name(self) -> str:
        return "Каталог"

    @property
    def description(self) -> str:
        return "Управління анкетами"

    @property
    def icon(self) -> str:
        return "📋"

    # Feature flag for per-tenant enable/disable
    feature_flag = FeatureFlag.CATALOG_ENABLED
    is_enabled_by_default = True
```

## Module Lifecycle

### 1. Registration

```python
# core/modules/registry.py
ModuleRegistry.register("catalog", CatalogModule)
ModuleRegistry.register("booking", BookingModule)
ModuleRegistry.register("shop", ShopModule)
```

### 2. Setup (at startup)

```python
async def setup_modules(dp: Dispatcher, container: Container):
    for module_id, module_class in ModuleRegistry.get_all():
        module = module_class()
        if await module.is_active(tenant_id):
            router = module.get_router()
            dp.include_router(router)
            await module.setup(dp, app, container)
```

### 3. Per-Tenant Activation

```python
# Check if module is enabled for tenant
if await catalog_module.is_active(tenant_id):
    # Show menu button, enable handlers
    buttons = await catalog_module.get_menu_buttons(tenant_id)
```

## Adding New Module (1-2 days)

### Step 1: Create Module Class

```python
# core/modules/car_rental_module.py
from core.modules.base_module import BaseModule

class CarRentalModule(BaseModule):
    feature_flag = FeatureFlag.CAR_RENTAL_ENABLED
    is_enabled_by_default = False

    @property
    def module_id(self) -> str:
        return "car_rental"

    @property
    def display_name(self) -> str:
        return "Оренда авто"

    @property
    def description(self) -> str:
        return "Система оренди автомобілів"

    @property
    def icon(self) -> str:
        return "🚗"

    async def setup(self, dp, app, container):
        # Register handlers
        from handlers.modules import car_rental
        dp.include_router(car_rental.router)

    async def get_catalog_items(self, tenant_id, search_query=None, offset=0):
        # Return cars for search
        return await self.repository.get_available(tenant_id)
```

### Step 2: Register in ModuleRegistry

```python
# core/modules/__init__.py
from core.modules.registry import ModuleRegistry
from core.modules.car_rental_module import CarRentalModule

ModuleRegistry.register("car_rental", CarRentalModule)
```

### Step 3: Add Feature Flag

```python
# core/features/flags.py
class FeatureFlag(StrEnum):
    # ... existing flags
    CAR_RENTAL_ENABLED = "CAR_RENTAL_ENABLED"
```

### Step 4: Create Handlers

```python
# handlers/modules/car_rental.py
from aiogram import Router

router = Router(name="car_rental")

@router.message(F.text == "Оренда авто")
async def show_cars(message: Message):
    await message.answer("Доступні автомобілі:")
```

## Key Methods

| Method | Purpose |
|--------|---------|
| `is_active(tenant_id)` | Check if module enabled for tenant |
| `get_menu_buttons(tenant_id)` | Return menu buttons |
| `get_router()` | Return Aiogram router with handlers |
| `get_catalog_items()` | Return items for universal search |
| `show_menu(msg, action)` | Show module-specific menu |
| `setup(dp, app, container)` | Initialize module at startup |

## Feature Flags Integration

Each module can be linked to a feature flag for per-tenant enable/disable:

```python
class ShopModule(BaseModule):
    feature_flag = FeatureFlag.SHOP_ENABLED
    is_enabled_by_default = True
```

When a tenant disables the flag in Dashboard, `is_active()` returns `False` and the module's menu buttons and handlers are hidden.

## References

- Base module: `core/modules/base_module.py`
- Registry: `core/modules/registry.py`
- Feature flags: `core/features/flags.py`
