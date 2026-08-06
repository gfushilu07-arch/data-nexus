-- case: SQLT-PGX-002
-- Purpose: Bind reordered, repeated, nullable, integer, and text parameters without literal SQL substitution.
-- Expected: Positional values retain their identity and NULL remains a protocol NULL.
-- Dialect: postgres

SELECT $2::text AS second_value,
       $1::bigint AS first_value,
       $1::bigint AS repeated_value,
       $3::text AS nullable_value;
