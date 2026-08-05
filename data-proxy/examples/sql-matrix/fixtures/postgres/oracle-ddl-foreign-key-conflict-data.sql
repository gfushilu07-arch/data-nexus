-- oracle: SQLT-ORACLE-POSTGRES-DDL-FOREIGN-KEY-CONFLICT-DATA-V1
-- Purpose: Produce stable PostgreSQL parent and orphan-child rows for foreign-key conflicts.
-- Expected: One parent row and one orphan child row in deterministic order.
-- Dialect: postgres

SELECT 'CHILD', probe_id, parent_id
FROM sqlt_ddl_constraint
UNION ALL
SELECT 'PARENT', parent_id, parent_id
FROM sqlt_ddl_parent
ORDER BY 1, 2;
