-- oracle: SQLT-ORACLE-MYSQL-DDL-COLUMN-DATA-V1
-- Purpose: Produce stable MySQL rows for column-constraint lifecycle checks.
-- Expected: Two ordered rows preserve their original integer values.
-- Dialect: mysql

SELECT probe_id, probe_value
FROM sqlt_ddl_column
ORDER BY probe_id;
