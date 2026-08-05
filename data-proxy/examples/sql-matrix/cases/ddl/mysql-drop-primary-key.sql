-- case: SQLT-DDL-016
-- Purpose: Remove an existing MySQL primary key with dialect-specific syntax.
-- Expected: The primary key metadata disappears and both columns remain unchanged.
-- Dialect: mysql

ALTER TABLE sqlt_ddl_constraint DROP PRIMARY KEY;
