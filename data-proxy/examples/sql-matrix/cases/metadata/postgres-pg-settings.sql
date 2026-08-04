-- case: SQLT-META-018
-- Purpose: Verify read-only PostgreSQL pg_settings catalog access.
-- Expected: Allow returns server_version and TimeZone settings; deny blocks access.
-- Dialect: postgres

SELECT name, setting
FROM pg_settings
WHERE name IN ('server_version', 'TimeZone')
ORDER BY name;
