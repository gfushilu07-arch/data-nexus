-- case: SQLT-DDL-004
-- Purpose: Verify the stable backend error returned by a duplicate CREATE TABLE.
-- Expected: The statement fails with duplicate-table identity and leaves metadata unchanged.
-- Dialect: mysql, postgres

CREATE TABLE sqlt_ddl_duplicate (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(64) NOT NULL
);
