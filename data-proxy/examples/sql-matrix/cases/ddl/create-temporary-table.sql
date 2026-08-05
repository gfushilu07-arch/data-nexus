-- case: SQLT-DDL-014
-- Purpose: Create a temporary table scoped to the current database connection.
-- Expected: Only the creating connection can use the table and disconnect removes it.
-- Dialect: mysql, postgres

CREATE TEMPORARY TABLE sqlt_ddl_temp (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(16) NOT NULL
);
