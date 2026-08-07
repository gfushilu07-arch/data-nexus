-- case: SQLT-UNSUPPORTED-001
-- Purpose: Pin the fail-closed boundary for server-side PostgreSQL program execution.
-- Expected: The gateway reports unsupported without invoking a shell command.
-- Dialect: postgres

COPY sqlt_customers TO PROGRAM 'sqlt-unreachable-sentinel';
