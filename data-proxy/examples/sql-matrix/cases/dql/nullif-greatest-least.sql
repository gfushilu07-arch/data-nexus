-- case: SQLT-DQL-055
-- Purpose: Verify NULLIF plus GREATEST and LEAST over numeric literals.
-- Expected: One row returns NULL, 9, and 3 respectively.
-- Dialect: mysql, postgres

SELECT NULLIF(5, 5) AS cleared_value,
       GREATEST(3, 9, 4) AS greatest_value,
       LEAST(3, 9, 4) AS least_value;
