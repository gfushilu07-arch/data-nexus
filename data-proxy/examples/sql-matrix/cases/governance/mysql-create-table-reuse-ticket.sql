-- case: SQLT-GOV-006
-- Purpose: Prove the approval ticket cannot be replayed.
-- Expected: Reusing the consumed ticket is rejected and leaves no second table.
-- Dialect: mysql

-- @step ddl_ticket_reuse
/*dn_ticket:@TICKET@*/ CREATE TABLE sqlt_gov_ticket_reuse_t (
    id BIGINT PRIMARY KEY
);
