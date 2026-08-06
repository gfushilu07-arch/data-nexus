-- oracle: SQLT-ORACLE-POSTGRES-TCL-DDL-STATE-V1
-- Purpose: Inspect transactional DDL table and row visibility without assuming the table exists.
-- Expected: Emit exact table and row counts after the TCL DDL transaction finishes.
-- Dialect: postgres

SELECT COUNT(*) AS sqlt_ddl_exists
FROM information_schema.tables
WHERE table_schema = current_schema() AND table_name = 'sqlt_tcl_ddl' \gset
SELECT 'ddl_table', :sqlt_ddl_exists;
\if :sqlt_ddl_exists
SELECT 'ddl_rows', COUNT(*) FROM sqlt_tcl_ddl;
\else
SELECT 'ddl_rows', 0;
\endif
