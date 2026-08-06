-- case: SQLT-DDL-037
-- Purpose: Create a named view with deterministic projected column aliases.
-- Expected: sqlt_ddl_view exposes view_id then view_name from the source table.
-- Dialect: mysql, postgres

CREATE VIEW sqlt_ddl_view AS
SELECT source_id AS view_id, source_name AS view_name
FROM sqlt_ddl_view_source;
