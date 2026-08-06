-- case: SQLT-INVALID-010
-- Purpose: Verify PostgreSQL reports integer division by zero deterministically.
-- Expected: Evaluation fails with SQLSTATE 22012 and fixture state is unchanged.
-- Dialect: postgres

SELECT 1 / 0;
