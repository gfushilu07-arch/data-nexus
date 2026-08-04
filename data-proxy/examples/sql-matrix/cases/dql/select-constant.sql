-- case: SQLT-DQL-004
-- Purpose: Verify a SELECT containing only a deterministic integer constant and alias.
-- Expected: One row is returned with one_value equal to 1 and no backend side effects.
-- Dialect: mysql, postgres

SELECT 1 AS one_value;
