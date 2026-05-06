<div align="center">

<img src="https://img.shields.io/badge/SmartHire-Multi--Tenant%20SaaS-0A66C2?style=for-the-badge&logo=telegram&logoColor=white" alt="SmartHire" />

# SmartHire Showcase

### Open-source architecture patterns from a production Multi-tenant SaaS platform

This repository showcases architectural decisions and code patterns from SmartHire — a production-grade Telegram-based SaaS platform. All commercial-sensitive data has been removed; only the architectural essence remains.

[![Python](https://img.shields.io/badge/python-3.12%2B-3776AB?style=flat-square&logo=python&logoColor=white)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Aiogram](https://img.shields.io/badge/aiogram-3.26-2CA5E0?style=flat-square&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%20async-D71F00?style=flat-square)](https://docs.sqlalchemy.org/)
[![React](https://img.shields.io/badge/React-19%20%2B%20TS-61DAFB?style=flat-square&logo=react&logoColor=black)](dashboard/)

---

## 🎯 What This Repository Contains

This is **not** a runnable application. It's a collection of architectural patterns you can study and adapt:

| Artifact | Description |
|----------|-------------|
| **ADRs** | 4 architectural decision records (multi-tenancy, service layer, partitioning) |
| **Code Fragments** | TenantQueryBuilder, BillingLifecycle, money.py, StateMachine |
| **docker-compose.yml** | Development environment setup |
| **GitHub Actions** | Quality gate workflow (lint, type check, tests) |
| **.windsurfrules** | AI-assisted development protocol |

## 🏛️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          Telegram Users / Clients                        │
└──────────────┬───────────────────────────┬──────────────────────────────┘
               │                           │
        ┌──────▼──────┐            ┌───────▼────────┐
        │  Bot (aiogram 3.x) │    │  TG Mini App   │
        │  handlers/*        │    │  (React + TWA) │
        └──────┬───────────┘      └───────┬────────┘
               │                           │
┌──────────────▼───────────────────────────▼──────────────────────────────┐
│                     FastAPI Application (core/api/)                      │
├──────────────────────────────────────────────────────────────────────────┤
│           Middlewares: tenant_id_validator · rate_limit · billing_check │
├──────────────────────────────────────────────────────────────────────────┤
│   DI Container (dependency-injector)  ·  Startup Sequence (10 modules) │
├──────────────────────────────────────────────────────────────────────────┤
│  Module Federation (core/modules/)                                       │
├──────────────────────────────────────────────────────────────────────────┤
│  Repositories (tenant-scoped)   ·   Domain Entities   ·   Services      │
├──────────────────────────────────────────────────────────────────────────┤
│  PostgreSQL (asyncpg)   │   Redis 7 (FSM + cache + queue + rate limit)   │
└─────────────────────────┴────────────────────────────────────────────────┘
```

## 📁 Repository Structure

```
SmartHire-Showcase/
├── README.md                      # This file
├── docker-compose.yml             # Dev environment
├── .github/
│   └── workflows/
│       └── quality-gate.yml       # CI/CD pipeline
├── .windsurfrules                 # AI development protocol
├── adr/
│   ├── 0030_multitenancy_hardening.md
│   ├── 0032_service_layer_enforcement.md
│   ├── 0025_postgresql_partitioning.md
│   └── 0023_frontend_backend_contract.md
├── code/
│   ├── tenant_query_builder.py   # Tenant-safe SQL builder
│   ├── billing_lifecycle.py      # Subscription state machine
│   ├── money.py                  # Kopecks arithmetic
│   └── billing_state_machine.py  # Explicit FSM with compensation
├── docs/
│   ├── module_federation.md      # Adding new business modules
│   ├── di_container.md           # Dependency injection setup
│   └── dashboard.md              # React dashboard architecture
└── pyproject.toml                # Python dependencies
```

## 🔑 Key Patterns

### 1. Multi-Tenant Isolation (TenantQueryBuilder)

```python
from core.repositories.sqlalchemy_helpers import TenantQueryBuilder

# All queries automatically include tenant_id filter
builder = TenantQueryBuilder(tenant_id="tenant_123")
stmt = builder.select(Anketa).where(Anketa.status == "opened")
query, params = builder.compile(stmt)
# query: SELECT * FROM ankety WHERE status = $1 AND tenant_id = $2
```

### 2. Money as Integers (Kopecks)

```python
from core.payments.money import to_kopecks, to_uah

# NEVER use float for money
kopecks = to_kopecks("50.25")  # 5025
amount = to_uah(5025)          # Decimal('50.25')
```

### 3. Billing State Machine

```python
from core.billing.state_machine import SubscriptionStateMachine, BillingState

machine = SubscriptionStateMachine(
    gateway=gateway,
    bot=bot,
    cache=cache,
    tenant_id=tenant_id,
    initial_state=BillingState.TRIAL
)
await machine.activate(payment_id="pay_123", amount=5000)
# TRIAL → ACTIVE with compensating actions on failure
```

### 4. Module Federation

```python
from core.modules.base import BaseModule
from core.modules.registry import ModuleRegistry

class CatalogModule(BaseModule):
    async def setup(self, dp, app, container):
        # Register handlers, keyboards, states
        pass

    async def get_catalog_items(self, tenant_id: str) -> list[dict]:
        return await self.repository.get_active(tenant_id)

# Auto-discovery: 1-2 days to add new business direction
ModuleRegistry.register("catalog", CatalogModule)
```

## 🚀 Quick Start

### Development Environment

```bash
# Start PostgreSQL + Redis
docker compose up -d postgres redis

# Run type checking
uv run mypy core/

# Run linter
uv run ruff check .

# Run tests
uv run pytest
```

### Quality Gate

```bash
# Full quality check
uv run python scripts/quality_gate.py
```

## 🤖 AI-Assisted Development Framework

SmartHire uses a systematic approach to AI-assisted development with automated quality gates and anti-hallucination measures.

### .windsurfrules Protocol

The project uses `.windsurfrules` - a strict development protocol that ensures AI-generated code meets production standards:

```markdown
## Identity & Stack
Role: Senior Python Developer & QA Automation Engineer.
Stack: Python 3.12+, uv, Aiogram 3.x, SQLAlchemy 2.0 (async), React 19/TS.

## Coding Standards
1. Type Hints: 100% type hinting. Use | instead of Union.
2. Exceptions: Never use except Exception: pass. Use contextlib.suppress().
3. Docstrings: Google-style for every class and public function.
4. Pydantic V2: Use model_validate, model_dump, model_dump_json.

## Workflow
1. Plan Phase: Output step-by-step plan before writing code.
2. Code Phase: Write code adhering to standards.
3. Check Phase: Run ruff check --fix and ruff format.
4. Test Phase: Run pytest for the changed module.

## Quality Gate
Task is DONE only when:
1. ruff check . --fix and ruff format . pass
2. Local tests for the changed module are green
3. mypy passes without errors
```

### Quality Gate Script

The project includes an automated quality gate that runs before each commit:

```python
# QualityGate class runs:
# - Pyright (type checking)
# - Bandit (security scan)
# - Ruff (linting + complexity)
# - Vulture (dead code)
# - FawltyDeps (unused imports)
# - AI Code Inspector (AI-specific patterns)
```

### Anti-Hallucination Measures

| Level | Tool | Purpose |
|-------|------|---------|
| Iron Gates | mypy strict | Catch type errors |
| Iron Gates | ruff | Lint + code style |
| Iron Gates | Pydantic v2 | Validate all inputs |
| Truth Serum | mutmut | Mutation testing |
| AI-Revisor | semgrep | Project-specific rules |

### CI/CD Pipeline

```yaml
# .github/workflows/quality-gate.yml
jobs:
  lint:
    run: uv run ruff check .
  type-check:
    run: uv run mypy code/ --ignore-missing-imports
  test:
    run: uv run pytest code/ -v
  security:
    run: uv run bandit -r code/
```

## 📚 Documentation

| Topic | File |
|-------|------|
| Multi-tenancy | `adr/0030_multitenancy_hardening.md` |
| Service Layer | `adr/0032_service_layer_enforcement.md` |
| PostgreSQL Partitioning | `adr/0025_postgresql_partitioning.md` |
| Frontend Contract | `adr/0023_frontend_backend_contract.md` |
| Module Federation | `docs/module_federation.md` |
| DI Container | `docs/di_container.md` |
| Dashboard | `docs/dashboard.md` |

## 🛠 Tech Stack

- **Python 3.12+**, **aiogram 3.x**, **FastAPI**
- **SQLAlchemy 2.0 async** + **asyncpg** + **Alembic**
- **Pydantic v2**, **dependency-injector**
- **React 19** + **TypeScript** + **shadcn/ui**
- **PostgreSQL 14+**, **Redis 7**
- **pytest**, **hypothesis**, **ruff**, **mypy**

## 📄 License

This is open-source architecture showcase. See individual files for their respective licenses.

---

<div align="center">

**Built with architectural patterns from production SaaS**

</div>
