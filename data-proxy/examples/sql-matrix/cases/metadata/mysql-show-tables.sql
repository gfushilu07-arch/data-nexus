-- case: SQLT-META-001
-- Purpose: Verify MySQL metadata enumeration through SHOW TABLES.
-- Expected: Allow policies return the fixture table list; deny blocks the statement.
-- Dialect: mysql

SHOW TABLES;
