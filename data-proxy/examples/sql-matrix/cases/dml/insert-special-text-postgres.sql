-- case: SQLT-DML-009
-- Purpose: Verify PostgreSQL E-string quote escaping, a literal backslash, and UTF-8 text.
-- Expected: The description contains quote ' slash \ and UTF-8 中文 exactly once each.
-- Dialect: postgres

INSERT INTO sqlt_mutations (mutation_id, description, amount, status)
VALUES (3008, E'quote '' slash \\ utf8 中文', 60.00, 'text');
