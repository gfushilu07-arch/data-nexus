-- case: SQLT-XBND-003
-- Purpose: Verify NULL, integer, decimal, quoted text, and datetime prepared parameters cross-protocol.
-- Expected: One row echoes all five bound values with stable normalization.
-- Dialect: mysql

-- @step select
SELECT ? AS null_value, ? AS int_value, ? AS decimal_value,
       ? AS text_value, ? AS datetime_value;
