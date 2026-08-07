-- case: SQLT-UNSUPPORTED-002
-- Purpose: Pin the fail-closed boundary for PostgreSQL server-side file COPY.
-- Expected: A restricted direct user is denied and the gateway rejects before backend execution.
-- Dialect: postgres

COPY sqlt_customers TO '/sqlt-unreachable-sentinel';
