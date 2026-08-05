-- case: SQLT-DQL-086
-- Purpose: Verify a deterministic ten-thousand-row result can be consumed incrementally.
-- Expected: Integers 1 through 10000 are returned in ascending order without gaps.
-- Dialect: mysql, postgres

WITH digits(n) AS (
    SELECT 0
    UNION ALL SELECT 1
    UNION ALL SELECT 2
    UNION ALL SELECT 3
    UNION ALL SELECT 4
    UNION ALL SELECT 5
    UNION ALL SELECT 6
    UNION ALL SELECT 7
    UNION ALL SELECT 8
    UNION ALL SELECT 9
)
SELECT ones.n
       + (tens.n * 10)
       + (hundreds.n * 100)
       + (thousands.n * 1000)
       + 1 AS sequence_id
FROM digits AS ones
CROSS JOIN digits AS tens
CROSS JOIN digits AS hundreds
CROSS JOIN digits AS thousands
ORDER BY sequence_id;
