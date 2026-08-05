-- case: SQLT-DQL-077
-- Purpose: Verify PostgreSQL expands a JSON array with deterministic ordinality.
-- Expected: Three status values are returned in their original array order.
-- Dialect: postgres

SELECT ordinal, status
FROM jsonb_array_elements_text('["paid", "pending", "refunded"]'::JSONB)
     WITH ORDINALITY AS item(status, ordinal)
ORDER BY ordinal;
