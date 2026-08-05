-- case: SQLT-DDL-019
-- Purpose: Add a named foreign key from the probe table to its parent table.
-- Expected: The foreign key maps parent_id to sqlt_ddl_parent.parent_id.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_constraint
ADD CONSTRAINT sqlt_fk_probe
FOREIGN KEY (parent_id) REFERENCES sqlt_ddl_parent (parent_id);
