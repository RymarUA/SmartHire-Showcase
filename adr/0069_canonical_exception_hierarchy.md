# ADR 0069: Canonical Exception Hierarchy — one class object per name

**Status:** Active
**Date:** 2026-10-13
**Author:** SmartHire Architecture Team

## Context

The codebase ran **two parallel service-exception hierarchies with the same names
but different class objects**. `shared/exceptions/__init__.py` defined
`BusinessLogicError`, `PaymentProcessingError`, `SubscriptionError`, … directly
under the base exception; `shared/exceptions/service.py` defined a second, richer
tree with the same names — none of which inherited from the first set.

`core/exceptions` re-exported a mix of both, so the object bound to
`SubscriptionError` depended on which import path a caller used. Consequences:

- `except BusinessLogicError` did **not** catch service-layer raises —
  `isinstance` checked the wrong class object, service errors fell through the
  API status map to the base-exception catch-all and returned **500** where
  400/503 was intended.
- Error-classification helpers had to check every error against two parallel tuples.
- A test pinned the defect as "documented behavior" instead of the intended contract.

## Decision

One canonical hierarchy, **one class object per name**:

```
SmartHireBaseException
└── ServiceError
    ├── ValidationError
    ├── ResourceNotFoundError
    ├── ConfigurationError
    └── BusinessLogicError
        ├── PaymentProcessingError      → HTTP 503 (retryable)
        ├── SubscriptionError           → HTTP 503 (retryable)
        ├── InsufficientStock
        └── OnboardingError             → HTTP 400
            └── TenantCreationError     → HTTP 500
                └── TokenAlreadyRegisteredError → HTTP 409
```

- The base lives in a **leaf module** (`exceptions_base.py`, no package imports) —
  routing it through the package `__init__` would create a package↔submodule
  import cycle, which the circular-import ratchet (ADR 0058) fails on any new SCC.
- `core/exceptions/*` stays a pure re-export facade: every name binds the same
  class object regardless of import path.
- The API `status_map` ordering is load-bearing (`isinstance` + first match):
  a parent listed above its subclass silently remaps that subtree — the order is
  pinned by tests.
- Every service exception inherits the base constructor and carries structured
  metadata uniformly: `error_code`, `tenant_id`, `correlation_id`.

## Consequences

- **Positive:** `except BusinessLogicError` catches every service-layer business
  error; HTTP status mapping is honest (400 for caller mistakes, 503 for
  retryable service outages); classification helpers check one hierarchy.
- **Negative:** code that relied on `except BusinessLogicError` *not* catching
  `OnboardingError` changed behavior — verified safe on the happy path; the
  compensation saga's coverage gap for `SubscriptionError` is a named follow-up,
  not silently ignored.
- **Neutral:** import-path diversity (`shared.exceptions` vs `core.exceptions`)
  remains deliberately for backward compatibility — all paths resolve to one
  object, pinned by an identity test.

## Key Pattern

```python
# Identity pin (test): same class object through every import path
assert shared.exceptions.BusinessLogicError is core.exceptions.BusinessLogicError

# Status map: subclass-specific statuses FIRST, generic parent LAST
status_map = [
    (TokenAlreadyRegisteredError, 409),
    (SubscriptionError, 503),        # before BusinessLogicError!
    (BusinessLogicError, 400),
    (ServiceError, 500),             # catch-all, last
]
```

## References

- Circular-import ratchet (why the base is a leaf): ADR 0058
- Service layer enforcement (exceptions as the layer's error contract): ADR 0032
