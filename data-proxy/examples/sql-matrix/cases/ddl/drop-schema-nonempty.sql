-- case: SQLT-DDL-045
-- Purpose: Attempt to drop a PostgreSQL schema that still contains a table.
-- Expected: Execution fails with dependent_objects_still_exist and preserves all objects.
-- Dialect: postgres

DROP SCHEMA sqlt_ddl_schema;
