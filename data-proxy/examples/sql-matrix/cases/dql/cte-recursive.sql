-- case: SQLT-DQL-040
-- Purpose: Verify a bounded recursive CTE reaches its termination predicate.
-- Expected: The integer sequence 1 through 4 is returned exactly once.
-- Dialect: mysql, postgres

WITH RECURSIVE sequence_values (value) AS (
    SELECT 1
    UNION ALL
    SELECT value + 1
    FROM sequence_values
    WHERE value < 4
)
SELECT value
FROM sequence_values
ORDER BY value;
