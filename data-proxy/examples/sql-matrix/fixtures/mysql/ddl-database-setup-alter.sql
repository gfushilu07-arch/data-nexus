-- fixture: SQLT-FIXTURE-MYSQL-DDL-DATABASE-SETUP-ALTER-V1
-- Purpose: Create the ALTER DATABASE target with stable metadata using root privileges.
-- Expected: The target starts with utf8mb4 and utf8mb4_0900_ai_ci.
-- Dialect: mysql

DROP DATABASE IF EXISTS sqlt_ddl_boundary_alter;
CREATE DATABASE sqlt_ddl_boundary_alter
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
