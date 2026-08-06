-- case: SQLT-INVALID-014
-- Purpose: Verify malformed MySQL binary parameter counts and types fail on the wire.
-- Expected: Every malformed execute is rejected, then a valid execute succeeds on the same connection.
-- Dialect: mysql

SELECT ? + 1 AS calculated_value;
