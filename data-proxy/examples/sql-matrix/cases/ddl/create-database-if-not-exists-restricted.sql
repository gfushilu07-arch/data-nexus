-- case: SQLT-DDL-054
-- Purpose: Attempt CREATE DATABASE IF NOT EXISTS through the restricted SQLT account.
-- Expected: IF NOT EXISTS does not bypass the database privilege boundary.
-- Dialect: mysql

CREATE DATABASE IF NOT EXISTS sqlt_ddl_boundary_if_not_exists
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
