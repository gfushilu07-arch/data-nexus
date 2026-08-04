-- case: SQLT-META-007
-- Purpose: Verify MySQL table status metadata for a single fixture table.
-- Expected: Allow returns one InnoDB status row; deny blocks the statement.
-- Dialect: mysql

SHOW TABLE STATUS LIKE 'sqlt_orders';
