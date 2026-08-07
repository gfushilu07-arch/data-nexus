-- oracle: SQLT-ORACLE-POSTGRES-UNSUPPORTED-STATE-V1
-- Purpose: Capture data, setting-file, role, and procedure state around unsupported SQL.
-- Expected: Every value remains byte-identical before and after a direct or gateway attempt.
-- Dialect: postgres

SELECT
    (SELECT COUNT(*) FROM sqlt_customers),
    (SELECT COUNT(*) FROM sqlt_orders),
    (SELECT COUNT(*) FROM sqlt_mutations),
    (SELECT COUNT(*) FROM sqlt_dml_targets);
SELECT setting FROM pg_settings WHERE name = 'work_mem';
SELECT COALESCE(
    (SELECT setting FROM pg_file_settings WHERE name = 'work_mem' ORDER BY sourceline DESC LIMIT 1),
    '<none>'
);
SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls
FROM pg_roles
WHERE rolname = 'sqlt';
SELECT COUNT(*)
FROM pg_proc
WHERE proname = 'sqlt_missing_procedure';
