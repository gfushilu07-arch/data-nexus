-- case: SQLT-TCL-010
-- Purpose: Expose the dialect difference for DDL followed by ROLLBACK.
-- Expected: MySQL keeps the implicitly committed table while PostgreSQL removes it.
-- Dialect: mysql, postgres

BEGIN;
CREATE TABLE sqlt_tcl_ddl (probe_id INTEGER NOT NULL PRIMARY KEY);
INSERT INTO sqlt_tcl_ddl (probe_id) VALUES (1);
ROLLBACK;
SELECT 'SQLT_TXN', 'ddl-rollback-complete';
