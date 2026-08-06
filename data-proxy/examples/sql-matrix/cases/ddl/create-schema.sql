-- case: SQLT-DDL-042
-- Purpose: Create a named PostgreSQL schema with the session user as owner.
-- Expected: sqlt_ddl_schema exists with owner sqlt and contains no objects.
-- Dialect: postgres

CREATE SCHEMA sqlt_ddl_schema;
