-- case: SQLT-META-003
-- Purpose: Verify MySQL database enumeration through SHOW DATABASES.
-- Expected: Allow returns visible databases; deny blocks metadata enumeration.
-- Dialect: mysql

SHOW DATABASES;
