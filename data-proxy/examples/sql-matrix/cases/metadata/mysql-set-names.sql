-- case: SQLT-META-010
-- Purpose: Verify MySQL SET NAMES changes only the current session character set.
-- Expected: The follow-up query returns utf8mb4 for client, connection, and results.
-- Dialect: mysql

SET NAMES utf8mb4;
SELECT @@session.character_set_client,
       @@session.character_set_connection,
       @@session.character_set_results;
