-- case: SQLT-DDL-051
-- Purpose: Attempt to alter a PostgreSQL sequence that does not exist.
-- Expected: Execution fails with undefined_table and leaves sequence metadata empty.
-- Dialect: postgres

ALTER SEQUENCE sqlt_ddl_sequence INCREMENT BY 7;
