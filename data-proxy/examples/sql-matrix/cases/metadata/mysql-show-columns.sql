-- case: SQLT-META-004
-- Purpose: Verify MySQL column metadata, types, nullability, keys, and defaults.
-- Expected: Allow returns the deterministic sqlt_customers column definition.
-- Dialect: mysql

SHOW COLUMNS FROM sqlt_customers;
