-- case: SQLT-XBND-003
-- Purpose: Verify NULL, integer, decimal, quoted text, and datetime extended parameters cross-protocol.
-- Expected: One row echoes all five bound values with stable normalization.
-- Dialect: postgres

-- @step select
SELECT $1 AS null_value, $2 AS int_value, $3 AS decimal_value,
       $4 AS text_value, $5 AS datetime_value;
