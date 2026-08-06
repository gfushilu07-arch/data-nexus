-- case: SQLT-DDL-040
-- Purpose: Attempt to create a view that references a missing source table.
-- Expected: Execution fails with a stable missing-relation error and creates no view metadata.
-- Dialect: mysql, postgres

CREATE VIEW sqlt_ddl_view AS
SELECT source_id AS view_id
FROM sqlt_ddl_view_missing_source;
