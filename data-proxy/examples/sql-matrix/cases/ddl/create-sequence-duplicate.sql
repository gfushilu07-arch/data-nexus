-- case: SQLT-DDL-050
-- Purpose: Attempt to create a PostgreSQL sequence whose name already exists.
-- Expected: Execution fails with duplicate_table and preserves all sequence state.
-- Dialect: postgres

CREATE SEQUENCE sqlt_ddl_sequence;
