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

The SQLT-3B DQL tranche currently contains 86 canonical cases
(`SQLT-DQL-001` through `SQLT-DQL-086`). The first 80 are deterministic
autocommit queries. Run their direct fixed-version backend acceptance with:

```bash
data-proxy/examples/sql-matrix/run-dql-corpus.sh
```

The runner resets the fixture before every case, executes each SQL file only against
its declared dialect, and strictly compares normalized output with the versioned
`dql-oracles.json`. It writes raw, normalized, expected and diff output plus
`results.jsonl` and `summary.json` to the external cache. It does not claim
cross-dialect equality; MySQL and PostgreSQL represent some literals and types
differently.

The complete default range currently performs 141 `case x dialect` executions.
The last fixed-version Docker acceptance passed all 141 comparisons; its summary
and per-case artifacts are stored below the configured external cache.

During corpus development, a bounded ID range can be selected with
`SQLT_DQL_CASE_FROM` and `SQLT_DQL_CASE_TO`. Final acceptance must leave both unset
so the complete registered DQL corpus runs.

The final four cases exercise explicit row-lock transactions with two real
connections. Run their fixed-version direct and security-off gateway acceptance with:

```bash
data-proxy/examples/sql-matrix/run-dql-lock-corpus.sh
```

The lock runner verifies blocking until rollback, compatible shared locks, stable
MySQL errno/SQLSTATE and PostgreSQL SQLSTATE for `NOWAIT`, exact `SKIP LOCKED`
results, and transaction/connection recovery. Its default range performs 16
`case x dialect x path` executions. `SQLT_DQL_LOCK_CASE_FROM`,
`SQLT_DQL_LOCK_CASE_TO`, and `SQLT_DQL_LOCK_SOURCES` are development filters only;
final acceptance leaves all three unset.

The last two cases cover a one-mebibyte field and a deterministic 10,000-row
result. Run their fixed-version direct and security-off gateway acceptance with:

```bash
data-proxy/examples/sql-matrix/run-dql-boundary-corpus.sh
```

The boundary runner writes client stdout directly to the external cache and reads
it back in fixed 64 KiB chunks. It compares byte count, row count, maximum line
length, final-LF state, complete SHA-256, and first/last-line SHA-256 against
`dql-boundary-oracles.json`; the full output is never retained in a shell variable
or JSON oracle. Its default range performs eight `case x dialect x path`
executions. `SQLT_DQL_BOUNDARY_CASE_FROM`, `SQLT_DQL_BOUNDARY_CASE_TO`, and
`SQLT_DQL_BOUNDARY_SOURCES` are development filters only.

The DML corpus contains the SQLT-3C1 INSERT tranche and SQLT-3C2 UPDATE/DELETE
tranches (`SQLT-DML-003` through `SQLT-DML-043`). They cover values, defaults, exact
decimals, special text, INSERT SELECT, predicates, expressions, subqueries,
MySQL JOIN UPDATE/DELETE, PostgreSQL UPDATE FROM/DELETE USING, zero-row writes,
stable constraint errors, dialect-specific conflict handling, PostgreSQL RETURNING,
MERGE, data-modifying CTEs, savepoint rollback, and transaction error recovery. Run the fixed-version
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
complete default range, currently 64 `case x dialect` executions. Raw responses,
normalized state, affected rows, errors, diffs, `results.jsonl`, and `summary.json`
are written below `/Volumes/fushilu/.caches/data-nexus/sql-matrix/<run-id>/`.

The canonical DDL corpus starts with table lifecycle and CREATE semantics. Run the
fixed MySQL 8.0.42 and PostgreSQL 16.8 direct/security-off gateway matrix with:

```bash
data-proxy/examples/sql-matrix/run-ddl-corpus.sh
```

Every `case x dialect x path` execution rebuilds its own direct-backend baseline.
The runner compares ordered catalog snapshots with `ddl-oracles.json`; backend
errors must match a stable MySQL error number/SQLSTATE or PostgreSQL SQLSTATE, and
error/idempotency cases must leave the catalog unchanged. TRUNCATE additionally
compares exact before/after data probes. The default range through D1c1 performs 48
executions. `SQLT_DDL_CASE_FROM` and `SQLT_DDL_CASE_TO` are development
filters only; final acceptance leaves both unset. Raw client output, normalized
catalog state, errors, diffs, and summaries remain below the external cache root.
