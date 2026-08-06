-- case: SQLT-PGX-007
-- Purpose: Recover an extended-query connection from an Execute error at Sync.
-- Expected: SQLSTATE 22012 aborts the unit, queued work is ignored, and a later unit succeeds.
-- Dialect: postgres

-- @statement failing
SELECT 1 / $1::integer AS quotient;

-- @statement ignored
SELECT 999::integer AS ignored_value;

-- @statement recovered
SELECT $1::integer AS recovered_value;
