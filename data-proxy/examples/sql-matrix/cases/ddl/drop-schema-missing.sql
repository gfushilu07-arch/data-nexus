-- case: SQLT-DDL-046
-- Purpose: Attempt to drop a PostgreSQL schema that does not exist.
-- Expected: Execution fails with invalid_schema_name and leaves the namespace catalog empty.
-- Dialect: postgres

DROP SCHEMA sqlt_ddl_schema;
