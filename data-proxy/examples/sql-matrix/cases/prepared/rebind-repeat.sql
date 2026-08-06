-- case: SQLT-PRP-007
-- Purpose: Rebind two parameters across repeated executions of one prepared statement.
-- Expected: Integer, string, and NULL executions are independent with no stale values.
-- Dialect: mysql

SELECT %s AS left_value, %s AS right_value
