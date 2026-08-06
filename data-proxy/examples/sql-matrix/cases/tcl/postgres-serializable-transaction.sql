-- case: SQLT-TCL-009
-- Purpose: Start and commit a PostgreSQL serializable transaction.
-- Expected: The transaction reports serializable and commits without changing fixture state.
-- Dialect: postgres

BEGIN ISOLATION LEVEL SERIALIZABLE;
SELECT current_setting('transaction_isolation');
COMMIT;
SELECT 'SQLT_TXN', 'isolation', 'serializable';
