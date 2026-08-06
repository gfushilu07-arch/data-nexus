-- case: SQLT-DDL-044
-- Purpose: Attempt to create a PostgreSQL schema whose name already exists.
-- Expected: Execution fails with duplicate_schema and preserves the empty schema.
-- Dialect: postgres

CREATE SCHEMA sqlt_ddl_schema;
