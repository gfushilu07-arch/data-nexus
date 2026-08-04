-- case: SQLT-META-012
-- Purpose: Verify MySQL database selection and active-database inspection.
-- Expected: The follow-up query returns sqlt and no persistent data changes.
-- Dialect: mysql

USE sqlt;
SELECT DATABASE();
