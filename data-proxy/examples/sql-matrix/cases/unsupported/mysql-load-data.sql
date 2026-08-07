-- case: SQLT-UNSUPPORTED-005
-- Purpose: Pin the fail-closed boundary for MySQL server-side LOAD DATA.
-- Expected: A restricted direct user is denied and the gateway rejects before file access.
-- Dialect: mysql

LOAD DATA INFILE '/sqlt-unreachable-sentinel'
INTO TABLE sqlt_mutations;
