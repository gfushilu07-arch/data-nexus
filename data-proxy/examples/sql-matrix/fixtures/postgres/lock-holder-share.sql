-- fixture: SQLT-FIXTURE-POSTGRES-LOCK-HOLDER-SHARE
-- Purpose: Acquire the shared row lock used by the FOR SHARE compatibility case.
-- Expected: Row 4001 remains share-locked until the runner sends an explicit rollback.
-- Dialect: postgres

BEGIN;
SELECT target_id FROM sqlt_dml_targets WHERE target_id = 4001 FOR SHARE;
SELECT 'SQLT_HOLDER_READY';
