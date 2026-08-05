-- oracle: SQLT-ORACLE-MYSQL-DDL-FOREIGN-KEY-CONFLICT-DATA-V1
-- Purpose: Produce stable MySQL parent and orphan-child rows for foreign-key conflicts.
-- Expected: One parent row and one orphan child row in deterministic order.
-- Dialect: mysql

SELECT 'CHILD', probe_id, parent_id
FROM sqlt_ddl_constraint
UNION ALL
SELECT 'PARENT', parent_id, parent_id
FROM sqlt_ddl_parent
ORDER BY 1, 2;
