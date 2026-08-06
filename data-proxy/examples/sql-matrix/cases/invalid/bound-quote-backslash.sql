-- case: SQLT-INVALID-018
-- Purpose: Verify quotes, backslashes, semicolons, and comment markers remain bound data.
-- Expected: The exact payload round-trips and no embedded text executes as SQL.
-- Dialect: mysql, postgres

-- @statement mysql
SELECT ? AS bound_payload;
-- @statement postgres
SELECT $1::TEXT AS bound_payload;
