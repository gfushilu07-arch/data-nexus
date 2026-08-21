-- case: SQLT-XBND-004
-- Purpose: Verify repeated and deduplicated numbered placeholders rebind parameters by occurrence.
-- Expected: One row returns first, second, then first again from only two bound parameters.
-- Dialect: postgres

-- @step select
SELECT $1 AS first_v, $2 AS second_v, $1 AS first_again;
