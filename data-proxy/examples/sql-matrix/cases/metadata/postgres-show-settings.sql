-- case: SQLT-META-013
-- Purpose: Verify PostgreSQL SHOW returns deterministic session settings.
-- Expected: Allow returns the active transaction isolation level; deny blocks it.
-- Dialect: postgres

SHOW transaction_isolation;
