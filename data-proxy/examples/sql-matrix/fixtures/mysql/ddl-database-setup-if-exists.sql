-- fixture: SQLT-FIXTURE-MYSQL-DDL-DATABASE-SETUP-IF-EXISTS-V1
-- Purpose: Create the DROP DATABASE IF EXISTS target with stable metadata using root privileges.
-- Expected: The target uses utf8mb4 and utf8mb4_0900_ai_ci.
-- Dialect: mysql

DROP DATABASE IF EXISTS sqlt_ddl_boundary_if_exists;
CREATE DATABASE sqlt_ddl_boundary_if_exists
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
