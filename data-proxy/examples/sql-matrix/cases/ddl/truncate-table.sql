-- case: SQLT-DDL-013
-- Purpose: Remove every row from a table without changing its schema.
-- Expected: The row count becomes zero and the exact column metadata remains unchanged.
-- Dialect: mysql, postgres

TRUNCATE TABLE sqlt_ddl_truncate;
