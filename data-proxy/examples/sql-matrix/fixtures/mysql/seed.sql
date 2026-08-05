-- fixture: SQLT-FIXTURE-MYSQL-SEED-V1
-- Purpose: Seed deterministic tenants, nullable values, timestamps, and decimal amounts.
-- Expected: Four customers, six orders, and five DML targets exist; mutations remain empty.
-- Dialect: mysql

INSERT INTO sqlt_customers (customer_id, tenant_id, email, display_name) VALUES
    (101, 10, 'ada@example.test', 'Ada'),
    (102, 10, NULL, 'Lin'),
    (201, 20, 'grace@example.test', 'Grace'),
    (202, 20, 'edsger@example.test', 'Edsger');

INSERT INTO sqlt_orders
    (order_id, customer_id, tenant_id, total_amount, status, created_at)
VALUES
    (1001, 101, 10, 12.50, 'paid', '2026-01-01 01:02:03'),
    (1002, 101, 10, 99.99, 'paid', '2026-01-02 02:03:04'),
    (1003, 102, 10, 15.00, 'pending', '2026-01-03 03:04:05'),
    (2001, 201, 20, 42.25, 'paid', '2026-02-01 04:05:06'),
    (2002, 201, 20, 7.75, 'refunded', '2026-02-02 05:06:07'),
    (2003, 202, 20, 120.00, 'paid', '2026-02-03 06:07:08');

INSERT INTO sqlt_dml_targets
    (target_id, customer_id, tenant_id, description, amount, status)
VALUES
    (4001, 101, 10, 'alpha', 10.00, 'new'),
    (4002, 102, 10, 'beta', 20.00, 'new'),
    (4003, 201, 20, 'gamma', 30.00, 'ready'),
    (4004, 202, 20, 'delta', NULL, 'ready'),
    (4005, 101, 10, 'epsilon', 50.00, 'archived');
