-- case: SQLT-DDL-056
-- Purpose: Attempt DROP DATABASE IF EXISTS on a root-prepared database as the restricted account.
-- Expected: IF EXISTS does not bypass the database privilege boundary.
-- Dialect: mysql

DROP DATABASE IF EXISTS sqlt_ddl_boundary_if_exists;
