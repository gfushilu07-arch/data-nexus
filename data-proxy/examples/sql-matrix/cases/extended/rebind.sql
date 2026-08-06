-- case: SQLT-PGX-003
-- Purpose: Rebind one named statement and portal with fresh parameter values.
-- Expected: Each execution observes only its current binding and resets prior portal state.
-- Dialect: postgres

SELECT $1::integer AS bound_value;
