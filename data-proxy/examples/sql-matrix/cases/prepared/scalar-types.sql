-- case: SQLT-PRP-004
-- Purpose: Bind decimal, date, time, and datetime scalar values.
-- Expected: Binary parameter and result codecs preserve deterministic value and precision.
-- Dialect: mysql

SELECT CAST(%s AS DECIMAL(12, 2)) AS decimal_value,
       CAST(%s AS DATE) AS date_value,
       CAST(%s AS TIME) AS time_value,
       CAST(%s AS DATETIME) AS datetime_value
