-- case: SQLT-META-014
-- Purpose: Verify PostgreSQL reports the active schema and search path.
-- Expected: Allow returns public and the configured search path without side effects.
-- Dialect: postgres

SELECT current_schema(), current_setting('search_path');
