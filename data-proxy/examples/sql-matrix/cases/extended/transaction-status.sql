-- case: SQLT-PGX-008
-- Purpose: Observe ReadyForQuery idle, transaction, failed-transaction, and recovered status bytes.
-- Expected: Extended units produce the deterministic status sequence T, T, E, and I.
-- Dialect: postgres

-- @statement begin
BEGIN;

-- @statement success
SELECT $1::integer AS transaction_value;

-- @statement failing
SELECT 1 / $1::integer AS quotient;

-- @statement rollback
ROLLBACK;
