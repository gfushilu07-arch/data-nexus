-- case: SQLT-DDL-001
-- Purpose: Verify portable table creation, alteration, and removal.
-- Expected: Allow completes the lifecycle; deny or missing ticket creates no object.
-- Dialect: mysql, postgres

CREATE TABLE sqlt_ddl_probe (
    probe_id INTEGER NOT NULL PRIMARY KEY,
    probe_name VARCHAR(64) NOT NULL
);
ALTER TABLE sqlt_ddl_probe ADD COLUMN probe_note VARCHAR(128);
DROP TABLE sqlt_ddl_probe;
