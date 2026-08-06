-- case: SQLT-DDL-039
-- Purpose: Attempt to create a view whose name already exists.
-- Expected: Execution fails with a stable duplicate-object error and preserves the original view.
-- Dialect: mysql, postgres

CREATE VIEW sqlt_ddl_view AS
SELECT source_id AS view_id
FROM sqlt_ddl_view_source;
