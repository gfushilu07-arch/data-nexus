-- case: SQLT-PRP-003
-- Purpose: Bind and return NULL values through the prepared null bitmap.
-- Expected: NULL remains NULL and the companion predicate reports true.
-- Dialect: mysql

SELECT %s AS null_value, %s IS NULL AS is_null
