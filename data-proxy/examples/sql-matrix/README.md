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

Run the SQLT-2 fixed-version Docker fixture and compare direct backend oracle output
with the security-off gateway path:

```bash
data-proxy/examples/sql-matrix/run-sql-fixture.sh
```

The fixture pins `mysql:8.0.42` and `postgres:16.8`, uses versioned dialect-specific
schema/seed/cleanup SQL files, and writes the run manifest, normalized output, logs,
results, binary/Git metadata, and summary below
`/Volumes/fushilu/.caches/data-nexus/sql-matrix/<run-id>/`.
The disposable database directories use bounded Docker `tmpfs` mounts, so database
files do not consume Docker Desktop's persistent disk. The runner removes its Compose
project and volumes on exit, including on failure. The acceptance compares read/state
snapshots, DML with savepoint rollback, DDL lifecycle state, and normalized MySQL and
PostgreSQL error identities; the last full run produced 10 passed comparisons.

A skipped case must include non-empty `reason`, `issue`, and `expires_when` fields.
The validator rejects missing files, unregistered SQL files, path traversal, duplicate
IDs, mismatched comments, unknown registry values, and ambiguous top-level outcomes.

The metadata/session/diagnostic tranche currently contains 20 canonical cases
(`SQLT-META-001` through `SQLT-META-020`) across MySQL and PostgreSQL. The corpus
budget test prevents this tranche from shrinking while DQL, DML, DDL, and failure
families are added.

The SQLT-3B DQL tranche currently contains 48 canonical cases
(`SQLT-DQL-001` through `SQLT-DQL-048`). Run its direct fixed-version backend
acceptance with:

```bash
data-proxy/examples/sql-matrix/run-dql-corpus.sh
```

The runner resets the fixture before every case, executes each SQL file only against
its declared dialect, and strictly compares normalized output with the versioned
`dql-oracles.json`. It writes raw, normalized, expected and diff output plus
`results.jsonl` and `summary.json` to the external cache. It does not claim
cross-dialect equality; MySQL and PostgreSQL represent some literals and types
differently.
