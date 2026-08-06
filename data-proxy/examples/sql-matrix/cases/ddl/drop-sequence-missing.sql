-- case: SQLT-DDL-052
-- Purpose: Attempt to drop a PostgreSQL sequence that does not exist.
-- Expected: Execution fails with undefined_table and leaves sequence metadata empty.
-- Dialect: postgres

DROP SEQUENCE sqlt_ddl_sequence;
