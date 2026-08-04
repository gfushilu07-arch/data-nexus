-- case: SQLT-META-002
-- Purpose: Verify PostgreSQL table enumeration through information_schema.
-- Expected: Allow policies return public fixture tables; deny blocks the statement.
-- Dialect: postgres

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
