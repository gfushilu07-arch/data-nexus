-- fixture: SQLT-FIXTURE-MYSQL-DDL-DATABASE-CLEANUP-V1
-- Purpose: Remove every D3d target database between restricted-account cases.
-- Expected: No database under the sqlt_ddl_boundary_ prefix remains.
-- Dialect: mysql

DROP DATABASE IF EXISTS sqlt_ddl_boundary_create;
DROP DATABASE IF EXISTS sqlt_ddl_boundary_if_not_exists;
DROP DATABASE IF EXISTS sqlt_ddl_boundary_drop;
DROP DATABASE IF EXISTS sqlt_ddl_boundary_if_exists;
DROP DATABASE IF EXISTS sqlt_ddl_boundary_alter;
