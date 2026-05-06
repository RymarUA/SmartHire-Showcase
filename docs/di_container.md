# Dependency Injection Container

SmartHire uses `dependency-injector` library for IoC container. All services are registered in the container and accessed via DI, avoiding global state and making testing easier.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     DIContainer                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Gateway    │  │  Services   │  │  Repos      │        │
│  │  (billing,  │  │  (anketa,   │  │  (anketa,   │        │
│  │   payment)  │  │   payment)  │  │   payment)  │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Cache      │  │  Scheduler  │  │  Config     │        │
│  └─────────────┘  └─────────────┘  └─────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Container Setup

```python
# core/di/container.py
from dependency_injector import containers, providers

class DIContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    # Database
    db_pool = providers.Singleton(
        DatabasePool,
        database_url=config.database_url,
    )
    db_session = providers.Factory(
        DbSession,
        pool=db_pool,
    )

    # Gateways
    billing_gateway = providers.Factory(
        BillingGateway,
        session=db_session,
    )
    payment_gateway = providers.Factory(
        PaymentGateway,
        session=db_session,
    )

    # Services
    anketa_service = providers.Factory(
        AnketaService,
        gateway=anketa_gateway,
    )
    payment_service = providers.Factory(
        PaymentService,
        gateway=payment_gateway,
    )

    # Cache
    redis_client = providers.Singleton(
        RedisClient,
        host=config.redis_host,
        port=config.redis_port,
    )
    cache = providers.Factory(
        TenantCache,
        redis=redis_client,
    )
```

## Initialization

```python
# main.py
from core.di import init_container, set_bot, set_dispatcher

async def main():
    # Initialize container with config
    container = init_container(
        database_url=os.getenv("DATABASE_URL"),
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
    )

    # Set runtime dependencies
    set_bot(bot)
    set_dispatcher(dp)

    # Start application
    await dp.start_polling(bot)
```

## Using in Handlers

```python
# handlers/anketa.py
from core.di import get_anketa_service

@router.message(F.text == "Мої анкети")
async def show_anketa(message: Message, state: FSMContext):
    # Get service from container
    anketa_service = get_anketa_service()

    # Use service (no direct DB access)
    ankety = await anketa_service.get_all(tenant_id)

    await message.answer(f"Знайдено {len(ankety)} анкет")
```

## Using in Services

```python
# core/services/anketa.py
from core.repositories.anketa import AnketaGateway

class AnketaService:
    def __init__(self, gateway: AnketaGateway) -> None:
        self.gateway = gateway

    async def get_all(self, tenant_id: str) -> list[dict]:
        return await self.gateway.get_all(tenant_id)
```

## Key Functions

| Function | Purpose |
|----------|---------|
| `init_container(config)` | Initialize container with config |
| `get_container()` | Get container instance |
| `get_anketa_service()` | Get AnketaService |
| `get_payment_service()` | Get PaymentService |
| `get_gateway()` | Get gateway by type |
| `set_bot(bot)` | Set bot instance at runtime |
| `set_dispatcher(dp)` | Set dispatcher at runtime |
| `shutdown_container()` | Cleanup on shutdown |

## Benefits

1. **No Global State**: All dependencies injected, not imported globally
2. **Testability**: Easy to mock dependencies in tests
3. **Single Responsibility**: Each service has clear dependency list
4. **Runtime Configuration**: Config loaded from env, not hardcoded
5. **Lazy Initialization**: Services created only when needed

## Anti-Pattern: Don't Do This

```python
# BAD: Global import
from core.repositories.anketa import AnketaGateway
gateway = AnketaGateway(session)  # Creates dependency manually

# GOOD: Use container
from core.di import get_anketa_service
service = get_anketa_service()  # Container manages lifecycle
```

## References

- Container: `core/container.py`
- DI module: `core/di/`
- Services: `core/services/`
