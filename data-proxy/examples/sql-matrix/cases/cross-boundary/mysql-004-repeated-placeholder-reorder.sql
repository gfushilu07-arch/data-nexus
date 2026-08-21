-- case: SQLT-XBND-004
-- Purpose: Verify repeated positional placeholders bind in occurrence order cross-protocol.
-- Expected: One row returns the three bound values in placeholder order.
-- Dialect: mysql

-- @step select
SELECT ? AS first_v, ? AS second_v, ? AS first_again;
