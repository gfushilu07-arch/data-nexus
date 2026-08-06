-- case: SQLT-INVALID-011
-- Purpose: Verify PostgreSQL rejects invalid text-to-integer conversion.
-- Expected: Conversion fails with SQLSTATE 22P02 and fixture state is unchanged.
-- Dialect: postgres

SELECT CAST('not-an-integer' AS INTEGER);
