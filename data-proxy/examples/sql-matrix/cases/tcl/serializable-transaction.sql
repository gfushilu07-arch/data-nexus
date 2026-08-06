-- case: SQLT-TCL-008
-- Purpose: Start and commit a MySQL serializable transaction.
-- Expected: The transaction reports SERIALIZABLE and commits without changing fixture state.
-- Dialect: mysql

SET SESSION TRANSACTION ISOLATION LEVEL SERIALIZABLE;
START TRANSACTION;
SELECT @@transaction_isolation;
COMMIT;
SELECT 'SQLT_TXN', 'isolation', 'serializable';
