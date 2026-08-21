-- case: SQLT-XBND-012
-- Purpose: Verify numbered placeholder gaps fail closed without reaching the backend.
-- Expected: The gapped execute fails with a stable error; Sync returns idle and the complete retry returns its row.
-- Dialect: postgres

-- @step gap
SELECT $1 AS first_v, $3 AS second_v;
-- @step recovered
SELECT $1 AS first_v, $2 AS second_v;
