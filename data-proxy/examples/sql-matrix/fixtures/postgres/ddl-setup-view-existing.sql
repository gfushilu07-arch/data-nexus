-- fixture: SQLT-FIXTURE-POSTGRES-DDL-VIEW-EXISTING
-- Purpose: Create a PostgreSQL source table and the named view under test.
-- Expected: sqlt_ddl_view exposes view_id then view_name before DROP or duplicate CREATE.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_view_source (
    source_id INTEGER NOT NULL,
    source_name VARCHAR(32) NOT NULL
);

CREATE VIEW sqlt_ddl_view AS
SELECT source_id AS view_id, source_name AS view_name
FROM sqlt_ddl_view_source;
