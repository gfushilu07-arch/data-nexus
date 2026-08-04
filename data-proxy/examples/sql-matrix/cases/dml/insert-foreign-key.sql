-- case: SQLT-DML-012
-- Purpose: Verify an INSERT into orders fails when the customer foreign key is absent.
-- Expected: The statement fails with the backend foreign-key identity and leaves orders unchanged.
-- Dialect: mysql, postgres

INSERT INTO sqlt_orders (order_id, customer_id, tenant_id, total_amount, status, created_at)
VALUES (3012, 9999, 99, 80.00, 'invalid-customer', '2026-03-01 00:00:00');
