-- case: SQLT-DDL-053
-- Purpose: Attempt CREATE DATABASE through the restricted SQLT account.
-- Expected: MySQL rejects database creation with no catalog side effect.
-- Dialect: mysql

CREATE DATABASE sqlt_ddl_boundary_create
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
