-- Sanitized excerpt from SmartHire proprietary codebase.
-- Demonstrates PostgreSQL Row-Level Security setup for multi-tenant isolation.
-- FORCE ROW LEVEL SECURITY ensures the table owner cannot bypass policies.

-- ============================================================
-- 1. Enable RLS on tenant-scoped tables
-- ============================================================

ALTER TABLE ankety ENABLE ROW LEVEL SECURITY;
ALTER TABLE ankety FORCE ROW LEVEL SECURITY;

ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings FORCE ROW LEVEL SECURITY;

ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments FORCE ROW LEVEL SECURITY;

ALTER TABLE tenant_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_users FORCE ROW LEVEL SECURITY;

-- ============================================================
-- 2. Application role (used by asyncpg connection pool)
-- ============================================================

-- The app connects as `smarthire_app`, NOT as the table owner.
-- This role obeys RLS policies.
CREATE ROLE smarthire_app WITH LOGIN PASSWORD '{{ vault:DB_APP_PASSWORD }}';
GRANT CONNECT ON DATABASE smarthire TO smarthire_app;
GRANT USAGE ON SCHEMA public TO smarthire_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO smarthire_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO smarthire_app;

-- Analytics read-only role — also obeys RLS, but only SELECT.
CREATE ROLE analytics_readonly WITH LOGIN PASSWORD '{{ vault:DB_ANALYTICS_PASSWORD }}';
GRANT CONNECT ON DATABASE smarthire TO analytics_readonly;
GRANT USAGE ON SCHEMA public TO analytics_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO analytics_readonly;

-- ============================================================
-- 3. RLS policies — current_setting carries tenant_id set by app
-- ============================================================

-- The application executes:  SET LOCAL smarthire.tenant_id = '<uuid>';
-- at the start of every transaction (set in middleware / AsyncSession event).

CREATE POLICY tenant_isolation_ankety
    ON ankety
    AS RESTRICTIVE
    USING (tenant_id::text = current_setting('smarthire.tenant_id', true));

CREATE POLICY tenant_isolation_bookings
    ON bookings
    AS RESTRICTIVE
    USING (tenant_id::text = current_setting('smarthire.tenant_id', true));

CREATE POLICY tenant_isolation_payments
    ON payments
    AS RESTRICTIVE
    USING (tenant_id::text = current_setting('smarthire.tenant_id', true));

CREATE POLICY tenant_isolation_tenant_users
    ON tenant_users
    AS RESTRICTIVE
    USING (tenant_id::text = current_setting('smarthire.tenant_id', true));

-- ============================================================
-- 4. Composite indexes — tenant_id FIRST for RLS performance
-- ============================================================
-- Without (tenant_id, ...) indexes, every policy check triggers a seq scan.

CREATE INDEX CONCURRENTLY idx_ankety_tenant_created
    ON ankety (tenant_id, created_at DESC);

CREATE INDEX CONCURRENTLY idx_bookings_tenant_status
    ON bookings (tenant_id, status);

CREATE INDEX CONCURRENTLY idx_payments_tenant_created
    ON payments (tenant_id, created_at DESC);

-- ============================================================
-- 5. Verify RLS is enforced (CI sanity check query)
-- ============================================================
-- Run as smarthire_app with NO tenant_id set — must return 0 rows.

SELECT count(*) FROM ankety;
-- Expected: 0  (RLS filters everything when tenant_id setting is missing)
