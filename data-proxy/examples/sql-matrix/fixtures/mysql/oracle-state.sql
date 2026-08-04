-- oracle: SQLT-ORACLE-MYSQL-STATE-V1
-- Purpose: Assert fixture row counts, decimal totals, and an empty mutation workspace.
-- Expected: The single row is customers=4, orders=6, total=297.49, mutations=0.
-- Dialect: mysql

SELECT
    (SELECT COUNT(*) FROM sqlt_customers) AS customers,
    (SELECT COUNT(*) FROM sqlt_orders) AS orders,
    (SELECT SUM(total_amount) FROM sqlt_orders) AS order_total,
    (SELECT COUNT(*) FROM sqlt_mutations) AS mutations;
