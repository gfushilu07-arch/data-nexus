-- fixture: SQLT-FIXTURE-POSTGRES-DDL-FOREIGN-KEY-CONFLICT
-- Purpose: Create PostgreSQL parent and child tables whose child contains an orphan row.
-- Expected: Adding a foreign key over parent_id is rejected.
-- Dialect: postgres

CREATE TABLE sqlt_ddl_parent (
    parent_id INTEGER NOT NULL PRIMARY KEY
);

CREATE TABLE sqlt_ddl_constraint (
    probe_id INTEGER NOT NULL,
    parent_id INTEGER NOT NULL
);

INSERT INTO sqlt_ddl_parent (parent_id) VALUES (10);
INSERT INTO sqlt_ddl_constraint (probe_id, parent_id) VALUES (1, 99);
