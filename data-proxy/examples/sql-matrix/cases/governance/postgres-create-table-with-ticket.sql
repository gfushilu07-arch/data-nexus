-- case: SQLT-GOV-006
-- Purpose: Execute the approved DDL carrying its one-shot dn_ticket comment.
-- Expected: The ticketed CREATE TABLE succeeds exactly once.
-- Dialect: postgres

-- @step ddl_with_ticket
/*dn_ticket:@TICKET@*/ CREATE TABLE sqlt_gov_ticket_t (
    id BIGINT PRIMARY KEY,
    note VARCHAR(64) NOT NULL
);
