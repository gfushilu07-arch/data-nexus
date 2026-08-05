-- fixture: SQLT-FIXTURE-MYSQL-SCHEMA-V1
-- Purpose: Create the version 1 MySQL schema used by canonical SQL cases.
-- Expected: Four empty InnoDB tables exist with deterministic types and constraints.
-- Dialect: mysql

CREATE TABLE sqlt_customers (
    customer_id BIGINT NOT NULL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    email VARCHAR(255) NULL,
    display_name VARCHAR(128) NOT NULL
) ENGINE = InnoDB;

CREATE TABLE sqlt_orders (
    order_id BIGINT NOT NULL PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    tenant_id INTEGER NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT fk_sqlt_orders_customer
        FOREIGN KEY (customer_id) REFERENCES sqlt_customers (customer_id)
) ENGINE = InnoDB;

CREATE TABLE sqlt_mutations (
    mutation_id BIGINT NOT NULL PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    amount DECIMAL(12, 2) NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'new'
) ENGINE = InnoDB;

CREATE TABLE sqlt_dml_targets (
    target_id BIGINT NOT NULL PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    tenant_id INTEGER NOT NULL,
    description VARCHAR(64) NOT NULL,
    amount DECIMAL(12, 2) NULL,
    status VARCHAR(32) NOT NULL,
    CONSTRAINT fk_sqlt_dml_targets_customer
        FOREIGN KEY (customer_id) REFERENCES sqlt_customers (customer_id)
) ENGINE = InnoDB;
