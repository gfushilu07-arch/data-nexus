-- case: SQLT-UNSUPPORTED-006
-- Purpose: Pin the fail-closed boundary for MySQL OUTFILE and DUMPFILE writes.
-- Expected: A restricted direct user is denied and the gateway rejects both file-write forms.
-- Dialect: mysql

-- @step outfile mysql
SELECT 42 INTO OUTFILE '/sqlt-unreachable-outfile';
-- @step dumpfile mysql
SELECT 42 INTO DUMPFILE '/sqlt-unreachable-dumpfile';
