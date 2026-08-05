-- oracle: SQLT-ORACLE-POSTGRES-DDL-COLUMN-CONFLICT-VALUES-V1
-- Purpose: Produce stable PostgreSQL rows for the existing-NULL NOT NULL conflict.
-- Expected: Ordered IDs and values, with SQL NULL represented explicitly.
-- Dialect: postgres

SELECT
    probe_id,
    COALESCE(probe_value::text, '<NULL>')
FROM sqlt_ddl_column
ORDER BY probe_id;
