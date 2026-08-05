-- case: SQLT-DDL-028
-- Purpose: Add a named foreign key while the child table contains an orphan row.
-- Expected: The statement fails without creating the foreign key or changing table data.
-- Dialect: mysql, postgres

ALTER TABLE sqlt_ddl_constraint
ADD CONSTRAINT sqlt_fk_conflict
FOREIGN KEY (parent_id) REFERENCES sqlt_ddl_parent (parent_id);
