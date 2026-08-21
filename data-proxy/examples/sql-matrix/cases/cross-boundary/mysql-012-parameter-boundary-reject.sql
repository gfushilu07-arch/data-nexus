-- case: SQLT-XBND-012
-- Purpose: Verify parameter arity boundaries fail closed without reaching the backend.
-- Expected: A missing binding fails with a stable error; the correctly bound retry returns its row.
-- Dialect: mysql

-- @step select
SELECT ? AS value;
