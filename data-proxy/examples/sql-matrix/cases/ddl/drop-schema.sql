-- case: SQLT-DDL-043
-- Purpose: Drop an existing empty PostgreSQL schema without using CASCADE.
-- Expected: sqlt_ddl_schema and its empty object set disappear.
-- Dialect: postgres

DROP SCHEMA sqlt_ddl_schema;
