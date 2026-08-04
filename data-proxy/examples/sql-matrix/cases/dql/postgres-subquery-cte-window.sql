-- case: SQLT-DQL-002
-- Purpose: Verify a PostgreSQL CTE containing a correlated subquery and window function.
-- Expected: Results match the oracle after configured column, mask, or row-limit rewrites.
-- Dialect: postgres

WITH ranked_orders AS (
    SELECT o.order_id, o.customer_id, o.total_amount,
           ROW_NUMBER() OVER (
               PARTITION BY o.customer_id
               ORDER BY o.total_amount DESC, o.order_id
           ) AS amount_rank
    FROM sqlt_orders AS o
    WHERE EXISTS (
        SELECT 1
        FROM sqlt_customers AS c
        WHERE c.customer_id = o.customer_id
    )
)
SELECT order_id, customer_id, total_amount, amount_rank
FROM ranked_orders
WHERE amount_rank <= 2
ORDER BY customer_id, amount_rank;
