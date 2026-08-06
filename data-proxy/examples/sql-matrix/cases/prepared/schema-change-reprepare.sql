-- case: SQLT-PRP-008
-- Purpose: Recover a prepared wildcard query after a concurrent result-schema change.
-- Expected: Error 2057 requires cursor rebind, then reprepare returns the two-column result.
-- Dialect: mysql

SELECT *
FROM sqlt_prepared_schema
ORDER BY probe_id
