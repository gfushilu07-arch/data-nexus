-- case: SQLT-DDL-055
-- Purpose: Attempt DROP DATABASE on a root-prepared database as the restricted SQLT account.
-- Expected: MySQL rejects the drop and preserves database metadata.
-- Dialect: mysql

DROP DATABASE sqlt_ddl_boundary_drop;
