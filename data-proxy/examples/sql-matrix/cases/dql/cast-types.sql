-- case: SQLT-DQL-056
-- Purpose: Verify portable CAST conversions from text to integral and decimal values.
-- Expected: One row returns numeric 42 and decimal 12.50.
-- Dialect: mysql, postgres

SELECT CAST('42' AS DECIMAL(10, 0)) AS integral_value,
       CAST('12.50' AS DECIMAL(6, 2)) AS decimal_value;
