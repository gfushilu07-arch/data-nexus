-- case: SQLT-DDL-038
-- Purpose: Drop an existing named view while preserving its source table.
-- Expected: sqlt_ddl_view disappears and sqlt_ddl_view_source remains unchanged.
-- Dialect: mysql, postgres

DROP VIEW sqlt_ddl_view;
