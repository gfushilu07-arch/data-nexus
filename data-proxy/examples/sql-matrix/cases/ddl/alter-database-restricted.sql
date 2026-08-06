-- case: SQLT-DDL-057
-- Purpose: Attempt ALTER DATABASE on a root-prepared database as the restricted SQLT account.
-- Expected: MySQL rejects the alter and preserves charset and collation metadata.
-- Dialect: mysql

ALTER DATABASE sqlt_ddl_boundary_alter
    CHARACTER SET latin1 COLLATE latin1_swedish_ci;
