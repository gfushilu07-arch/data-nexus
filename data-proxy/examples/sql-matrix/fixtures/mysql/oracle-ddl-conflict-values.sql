-- oracle: SQLT-ORACLE-MYSQL-DDL-CONFLICT-VALUES-V1
-- Purpose: Produce stable MySQL rows for UNIQUE, CHECK, and NOT NULL conflict checks.
-- Expected: Ordered IDs and values, with SQL NULL represented explicitly.
-- Dialect: mysql

SELECT
    probe_id,
    COALESCE(CAST(probe_value AS CHAR), '<NULL>')
FROM sqlt_ddl_constraint
ORDER BY probe_id;
