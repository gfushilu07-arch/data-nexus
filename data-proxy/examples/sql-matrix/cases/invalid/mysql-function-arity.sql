-- case: SQLT-INVALID-013
-- Purpose: Verify MySQL rejects an invalid native-function argument count.
-- Expected: Function validation fails with error 1582 and fixture state is unchanged.
-- Dialect: mysql

SELECT ROUND(1, 2, 3);
