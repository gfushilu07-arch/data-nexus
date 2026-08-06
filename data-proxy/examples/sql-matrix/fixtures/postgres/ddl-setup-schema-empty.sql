-- fixture: SQLT-FIXTURE-POSTGRES-DDL-SCHEMA-EMPTY
-- Purpose: Create the empty PostgreSQL schema used by lifecycle and duplicate-name cases.
-- Expected: sqlt_ddl_schema is owned by sqlt and contains no objects.
-- Dialect: postgres

CREATE SCHEMA sqlt_ddl_schema;
