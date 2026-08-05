-- oracle: SQLT-ORACLE-POSTGRES-DDL-COLUMN-DATA-V1
-- Purpose: Produce stable PostgreSQL rows for column-constraint lifecycle checks.
-- Expected: Two ordered rows preserve their original integer values.
-- Dialect: postgres

SELECT probe_id, probe_value
FROM sqlt_ddl_column
ORDER BY probe_id;
