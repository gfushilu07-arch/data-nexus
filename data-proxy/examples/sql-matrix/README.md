# SQL capability matrix

This directory is the canonical, machine-validated registry for SQL behavior across
Data Nexus dialects, frontends, backends, policy paths, and test profiles.

Each scenario is stored in a separate file below `cases/`. SQL text must not be
embedded in `manifest.json`. Every SQL file starts with these four comments:

```sql
-- case: SQLT-DQL-001
-- Purpose: Describe the behavior exercised by the statement.
-- Expected: Describe the observable result and side-effect contract.
-- Dialect: mysql, postgres
```

`capabilities.json` defines the accepted registry vocabulary. `manifest.json` maps
each case to its SQL file, capability, protocol, statement/transaction/parameter mode,
and contains an explicit outcome for every policy scenario.
The only accepted outcomes are `allow`, `rewrite`, `deny`, and `unsupported`;
`unknown` is never an accepted result.

Run the repository validation and its focused tests from the repository root:

```bash
python3 data-proxy/examples/sql-matrix/validate.py
PYTHONPYCACHEPREFIX=/Volumes/fushilu/.caches/data-nexus/python-cache \
  python3 -m unittest discover \
    -s data-proxy/examples/sql-matrix/tests \
    -p 'test_*.py'
```

A skipped case must include non-empty `reason`, `issue`, and `expires_when` fields.
The validator rejects missing files, unregistered SQL files, path traversal, duplicate
IDs, mismatched comments, unknown registry values, and ambiguous top-level outcomes.
