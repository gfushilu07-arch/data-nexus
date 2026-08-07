-- oracle: SQLT-ORACLE-MYSQL-UNSUPPORTED-STATE-V1
-- Purpose: Capture data, global setting, privilege, and routine state around unsupported SQL.
-- Expected: Every value remains byte-identical before and after a direct or gateway attempt.
-- Dialect: mysql

SELECT
    (SELECT COUNT(*) FROM sqlt_customers),
    (SELECT COUNT(*) FROM sqlt_orders),
    (SELECT COUNT(*) FROM sqlt_mutations),
    (SELECT COUNT(*) FROM sqlt_dml_targets);
SELECT @@GLOBAL.max_connections;
SELECT COUNT(*)
FROM information_schema.USER_PRIVILEGES
WHERE GRANTEE = '''sqlt''@''%'''
  AND PRIVILEGE_TYPE IN ('FILE', 'SUPER', 'SYSTEM_VARIABLES_ADMIN', 'PERSIST_RO_VARIABLES_ADMIN');
SELECT COUNT(*)
FROM information_schema.ROUTINES
WHERE ROUTINE_SCHEMA = 'sqlt'
  AND ROUTINE_NAME = 'sqlt_missing_procedure';
