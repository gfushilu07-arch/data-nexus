-- fixture: SQLT-FIXTURE-POSTGRES-SCHEMA-V1
-- Purpose: Create the version 1 PostgreSQL schema used by canonical SQL cases.
-- Expected: Three empty tables exist with deterministic types and constraints.
-- Dialect: postgres

CREATE TABLE sqlt_customers (
    customer_id BIGINT PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    email VARCHAR(255),
    display_name VARCHAR(128) NOT NULL
);

CREATE TABLE sqlt_orders (
    order_id BIGINT PRIMARY KEY,
    customer_id BIGINT NOT NULL REFERENCES sqlt_customers (customer_id),
    tenant_id INTEGER NOT NULL,
    total_amount NUMERIC(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL
);

CREATE TABLE sqlt_mutations (
    mutation_id BIGINT PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    amount NUMERIC(12, 2)
);
