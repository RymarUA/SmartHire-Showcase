# ADR-0023: PII Encryption Strategy

**Status:** Accepted  
**Date:** 2025-02-20  
**Last reviewed:** 2026-04-19

## Context

SmartHire stores personally identifiable information (PII): phone numbers, email addresses,
full names, and free-text answers from job applicants. A database breach without field-level
encryption exposes all PII in plaintext. Regulatory requirements (GDPR-adjacent) mandate
protection of PII at rest.

## Decision

Encrypt sensitive fields using **AES-256-GCM** (authenticated encryption) before writing to
PostgreSQL. Decryption happens in the application layer, never in SQL queries.

### Key material

- `PII_ENCRYPTION_KEY`: 32-byte secret, stored in environment / Vault, **never in code or DB**.
- `PII_ENCRYPTION_SALT`: 16-byte salt, stored separately. Compromising one does not expose both.
- Keys are rotated annually. Old ciphertext is re-encrypted during a scheduled migration job.

### Encrypted columns

| Table | Column | Type |
|-------|--------|------|
| `applicants` | `phone` | `TEXT` (AES-256-GCM ciphertext, base64) |
| `applicants` | `email` | `TEXT` |
| `applicants` | `full_name` | `TEXT` |
| `anketa_responses` | `free_text_answer` | `TEXT` |

### Encryption in SQLAlchemy

```python
from sqlalchemy import TypeDecorator, Text
from cryptography.fernet import Fernet

class EncryptedString(TypeDecorator):
    """SQLAlchemy column type that transparently encrypts/decrypts values."""

    impl = Text
    cache_ok = True

    def __init__(self, key: bytes) -> None:
        super().__init__()
        self._fernet = Fernet(key)

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self._fernet.decrypt(value.encode()).decode()
```

### PII in logs

`utils/masking.py` provides `mask_pii(text: str) -> str` — regex-based masker applied
to all structured log values before they leave the process (Logtail / Sentry destinations).

```python
mask_pii("+380971234567")   # → "+38097***4567"
mask_pii("user@example.com") # → "u***@example.com"
```

## Consequences

### Positive
- Database breach exposes only ciphertext — useless without key material.
- AES-256-GCM provides both confidentiality and integrity (detects tampering).
- Transparent TypeDecorator: service layer code reads/writes plaintext strings normally.
- Sentry and Logtail never receive raw PII.

### Negative
- Encrypted columns cannot be indexed or searched efficiently (full-table decrypt required for search).
  Mitigated by storing a hashed index: `SHA-256(normalize(phone))` for lookup.
- Key rotation requires a background job to re-encrypt all rows — scheduled during low-traffic window.
- Adds ~0.2ms per encrypt/decrypt call (negligible at current scale).

## References

- ADR-001: Multi-Tenant Architecture (encryption is applied after tenant_id isolation).
- ADR-0030: Multi-Tenancy Hardening (defense-in-depth: RLS + encryption + masking).
