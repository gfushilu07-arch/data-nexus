-- oracle: SQLT-ORACLE-MYSQL-TCL-DDL-STATE-V1
-- Purpose: Inspect transactional DDL table and row visibility without assuming the table exists.
-- Expected: Emit exact table and row counts after the TCL DDL transaction finishes.
-- Dialect: mysql

SELECT 'ddl_table', COUNT(*)
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'sqlt_tcl_ddl';
SET @sqlt_ddl_probe = IF(
    EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = 'sqlt_tcl_ddl'
    ),
    'SELECT ''ddl_rows'', COUNT(*) FROM sqlt_tcl_ddl',
    'SELECT ''ddl_rows'', 0'
);
PREPARE sqlt_ddl_probe_stmt FROM @sqlt_ddl_probe;
EXECUTE sqlt_ddl_probe_stmt;
DEALLOCATE PREPARE sqlt_ddl_probe_stmt;
