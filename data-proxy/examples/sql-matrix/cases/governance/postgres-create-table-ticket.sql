-- case: SQLT-GOV-006
-- Purpose: Verify DDL dual control with a one-shot approval ticket.
-- Expected: DDL without a ticket is rejected before any backend object is created.
-- Dialect: postgres

-- @step ddl_no_ticket
CREATE TABLE sqlt_gov_ticket_t (
    id BIGINT PRIMARY KEY,
    note VARCHAR(64) NOT NULL
);
