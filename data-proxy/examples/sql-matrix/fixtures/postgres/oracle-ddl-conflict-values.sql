-- oracle: SQLT-ORACLE-POSTGRES-DDL-CONFLICT-VALUES-V1
-- Purpose: Produce stable PostgreSQL rows for UNIQUE and CHECK conflict checks.
-- Expected: Ordered IDs and integer values from sqlt_ddl_constraint.
-- Dialect: postgres

SELECT
    probe_id,
    COALESCE(probe_value::text, '<NULL>')
FROM sqlt_ddl_constraint
ORDER BY probe_id;
