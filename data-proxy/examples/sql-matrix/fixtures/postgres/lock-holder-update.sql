-- fixture: SQLT-FIXTURE-POSTGRES-LOCK-HOLDER-UPDATE
-- Purpose: Acquire the exclusive row lock used by two-connection DQL lock cases.
-- Expected: Row 4001 remains update-locked until the runner sends an explicit rollback.
-- Dialect: postgres

BEGIN;
SELECT target_id FROM sqlt_dml_targets WHERE target_id = 4001 FOR UPDATE;
SELECT 'SQLT_HOLDER_READY';
