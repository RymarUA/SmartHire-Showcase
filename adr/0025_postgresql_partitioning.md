# ADR-0025: PostgreSQL Table Partitioning

**Status:** accepted
**Date:** 2026-04-24
**Author:** SmartHire Architecture Team

## Context

The PostgreSQL database contains several high-volume tables that grow linearly over time:

- `outbox_messages` — Telegram messages, webhooks, one per event. Can grow to millions of rows.
- `billing_payments` — Payment history, needs 7-year retention for financial audit.
- `audit_logs` — User action audit trail.

**Current problems:**
- Index bloat on large tables → slow queries.
- VACUUM takes hours on tables >50GB.
- Full table scans for time-range queries.
- Backup times increase linearly with data size.
- P99 query latency degrades as tables grow.

**Assumption:** Database will remain <100GB for the next 12 months.

## Decision

Implement **declarative partitioning** using PostgreSQL's native `PARTITION BY RANGE` feature, managed via `pg_partman` extension.

### Tables to Partition

| Table | Partition Key | Interval | Retention |
|-------|---------------|----------|-----------|
| `outbox_messages` | `created_at` | 1 month | 3 months |
| `billing_payments` | `created_at` | 1 month | 7 years |
| `audit_logs` | `created_at` | 1 month | 1 year |

### Partitioning Strategy

1. **pg_partman** — Automatic child table creation and retention-based drop.
2. **Partition by Range** — Monthly partitions for efficient time-range queries.
3. **No Partitioning** — `tenants`, `users`, `ankety`, `business_config`.

### Migration Approach (Blue-Green)

```sql
-- Step 1: Create new partitioned table
CREATE TABLE outbox_messages_new (LIKE outbox_messages INCLUDING ALL) 
PARTITION BY RANGE (created_at);

-- Step 2: Create initial partition
CREATE TABLE outbox_messages_2026_04 PARTITION OF outbox_messages_new
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

-- Step 3: Copy data (batched for large tables)
INSERT INTO outbox_messages_new SELECT * FROM outbox_messages;

-- Step 4: Rename atomically
ALTER TABLE outbox_messages RENAME TO outbox_messages_old;
ALTER TABLE outbox_messages_new RENAME TO outbox_messages;

-- Step 5: Drop old table after verification
DROP TABLE outbox_messages_old;
```

### pg_partman Configuration

```sql
CREATE EXTENSION pg_partman;

SELECT partman.create_parent(
    p_parent_table => 'public.outbox_messages',
    p_partition_by => '_RANGE',
    p_interval => '1 month',
    p_premake => 3,
    p_retention => '3 months',
    p_retention_keep_table => false
);
```

## Consequences

### Positive

- **Query performance**: Partition pruning for time-range queries.
- **VACUUM efficiency**: Each partition vacuumed independently.
- **Backup efficiency**: Can exclude old partitions from hot backup.
- **Automatic cleanup**: pg_partman drops old partitions automatically.
- **No application changes**: Queries work unchanged.

### Negative

- Migration complexity (blue-green rename required).
- Queries must include partition key for pruning.
- Global unique constraints require including partition key.
- Additional disk usage (~5-10% for indexes).

### Neutral

- Team learning curve.

## Alternatives Considered

| Alternative | Pros | Cons |
|-------------|------|------|
| No partitioning | Simple | Doesn't scale |
| TimescaleDB | Native auto-partitioning | Additional dependency |
| Manual range tables | No extension | Manual creation/deletion |
| Sharding by tenant_id | Scales horizontally | Much more complex |

## Implementation Notes

- PostgreSQL 14+ required
- `pg_partman` extension must be installed
- Run daily maintenance: `SELECT partman.run_maintenance_proc();`

## Review

- **Status:** Implemented
- **Success criteria:** `EXPLAIN` shows partition pruning, old partitions auto-dropped
