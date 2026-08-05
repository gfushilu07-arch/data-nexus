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

The SQLT-3B DQL tranche currently contains 64 canonical cases
(`SQLT-DQL-001` through `SQLT-DQL-064`). Run its direct fixed-version backend
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

During corpus development, a bounded ID range can be selected with
`SQLT_DQL_CASE_FROM` and `SQLT_DQL_CASE_TO`. Final acceptance must leave both unset
so the complete registered DQL corpus runs.

The DML corpus contains the SQLT-3C1 INSERT tranche and SQLT-3C2 UPDATE/DELETE
tranches (`SQLT-DML-003` through `SQLT-DML-035`). They cover values, defaults, exact
decimals, special text, INSERT SELECT, predicates, expressions, subqueries,
MySQL JOIN UPDATE/DELETE, PostgreSQL UPDATE FROM/DELETE USING, zero-row writes,
stable constraint errors, and dialect-specific conflict handling. Run the fixed-version
direct and security-off gateway
acceptance with:

```bash
data-proxy/examples/sql-matrix/run-dml-corpus.sh
```

Each case and dialect starts from a fresh fixture. Successful executions are compared
with the exact versioned state in `dml-oracles.json`; UPDATE/DELETE cases also compare
the affected-row count emitted by the fixed SQL clients. Failed executions must match
the MySQL error number and SQLSTATE or PostgreSQL SQLSTATE, and their before/after
state snapshots must be identical. Use `SQLT_DML_CASE_FROM` and
`SQLT_DML_CASE_TO` only for bounded development runs. Final acceptance runs the
complete default range, currently 55 `case x dialect` executions. Raw responses,
normalized state, affected rows, errors, diffs, `results.jsonl`, and `summary.json`
are written below `/Volumes/fushilu/.caches/data-nexus/sql-matrix/<run-id>/`.
