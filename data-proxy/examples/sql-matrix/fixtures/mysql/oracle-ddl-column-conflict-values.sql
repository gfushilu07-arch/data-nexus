-- oracle: SQLT-ORACLE-MYSQL-DDL-COLUMN-CONFLICT-VALUES-V1
-- Purpose: Produce stable MySQL rows for the existing-NULL NOT NULL conflict.
-- Expected: Ordered IDs and values, with SQL NULL represented explicitly.
-- Dialect: mysql

SELECT
    probe_id,
    COALESCE(CAST(probe_value AS CHAR), '<NULL>')
FROM sqlt_ddl_column
ORDER BY probe_id;
