-- case: SQLT-INVALID-021
-- Purpose: Verify PostgreSQL frontend messages at and above the fixed 16 MiB gateway limit.
-- Expected: The in-limit query completes, the over-limit connection closes, and a new connection recovers.
-- Dialect: postgres

-- @generate message_bytes=16777216 over_bytes=16777217
SELECT 1 AS generated_message_boundary;
