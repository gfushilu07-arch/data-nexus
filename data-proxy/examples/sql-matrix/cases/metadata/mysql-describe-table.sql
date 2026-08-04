-- case: SQLT-META-005
-- Purpose: Verify the MySQL DESCRIBE alias for table column metadata.
-- Expected: Allow matches SHOW COLUMNS shape; deny returns no metadata.
-- Dialect: mysql

DESCRIBE sqlt_orders;
