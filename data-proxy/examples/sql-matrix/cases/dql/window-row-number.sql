-- case: SQLT-DQL-046
-- Purpose: Verify ROW_NUMBER partitions by status and uses a deterministic amount ordering.
-- Expected: Every order receives a stable one-based position within its status partition.
-- Dialect: mysql, postgres

SELECT order_id, status,
       ROW_NUMBER() OVER (
           PARTITION BY status
           ORDER BY total_amount DESC, order_id
       ) AS status_position
FROM sqlt_orders
ORDER BY status, status_position;
