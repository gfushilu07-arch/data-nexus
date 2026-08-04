#!/usr/bin/env bash
# Run the SQLT-2 fixed-version database fixture and compare direct/backend output
# with the security-off gateway path. All run artifacts stay in the external cache.
set -euo pipefail

RUST_TOOLCHAIN_BIN="${RUST_TOOLCHAIN_BIN:-/Volumes/fushilu/.rustup/toolchains/1.94.1-aarch64-apple-darwin/bin}"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$RUST_TOOLCHAIN_BIN:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"
export CARGO_TARGET_DIR="${DATA_NEXUS_CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.94.1}"

ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT/../.." && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
COMPOSE_FILE="$ROOT/fixtures/docker-compose.yml"
GATEWAY_CONFIG="$ROOT/fixtures/gateway-config.toml"
COMPOSE_PROJECT="sqlt2-${RUN_ID//[^a-zA-Z0-9]/}"
GATEWAY_LOG="$RUN_DIR/logs/gateway.log"
RESULTS="$RUN_DIR/results.jsonl"

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/normalized-output"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"

COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE")
GATEWAY_PID=""

cleanup() {
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

need() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "missing required command: $1" >&2
    exit 1
  }
}

need docker
need curl
need python3

[[ "$(rustc --version)" == rustc\ 1.94.1\ * ]] || {
  echo "SQLT-2 requires rustc 1.94.1; found: $(rustc --version)" >&2
  exit 1
}

echo "SQLT-2 run: $RUN_ID"
echo "artifacts: $RUN_DIR"
echo "==> starting fixed-version MySQL 8.0.42 and PostgreSQL 16.8"
"${COMPOSE[@]}" up -d

for _ in $(seq 1 90); do
  mysql_ok="$("${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null || true)"
  pg_ok="$("${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt 2>/dev/null || true)"
  if [[ "$mysql_ok" == *"mysqld is alive"* && "$pg_ok" == *"accepting connections"* ]]; then
    break
  fi
  if [[ "$("${COMPOSE[@]}" ps --status exited -q | wc -l | tr -d ' ')" != "0" ]]; then
    "${COMPOSE[@]}" logs --no-color >"$RUN_DIR/logs/compose-startup.log" 2>&1 || true
    echo "a SQLT-2 database container exited during startup; see $RUN_DIR/logs/compose-startup.log" >&2
    exit 1
  fi
  sleep 2
done
"${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent
"${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt

run_mysql_sql() {
  local sql_file="$1"
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$sql_file"
}

run_postgres_sql() {
  local sql_file="$1"
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 -v VERBOSITY=verbose -A -t -F $'\t' \
    -U sqlt -d sqlt <"$sql_file"
}

run_mysql_gateway() {
  local sql_file="$1"
  docker run --rm -i --add-host=host.docker.internal:host-gateway mysql:8.0.42 \
    mysql --batch --raw --skip-column-names --ssl-mode=DISABLED \
    -h host.docker.internal -P 29088 -uroot -proot <"$sql_file"
}

run_postgres_gateway() {
  local sql_file="$1"
  docker run --rm -i --add-host=host.docker.internal:host-gateway postgres:16.8 \
    env PGPASSWORD=root psql -X -q -v ON_ERROR_STOP=1 -v VERBOSITY=verbose -A -t -F $'\t' \
    -h host.docker.internal -p 29089 -U root -d sqlt <"$sql_file"
}

load_fresh_fixtures() {
  run_mysql_sql "$ROOT/fixtures/mysql/cleanup.sql" >"$RUN_DIR/logs/mysql-cleanup.out"
  run_mysql_sql "$ROOT/fixtures/mysql/schema.sql" >"$RUN_DIR/logs/mysql-schema.out"
  run_mysql_sql "$ROOT/fixtures/mysql/seed.sql" >"$RUN_DIR/logs/mysql-seed.out"
  run_postgres_sql "$ROOT/fixtures/postgres/cleanup.sql" >"$RUN_DIR/logs/postgres-cleanup.out"
  run_postgres_sql "$ROOT/fixtures/postgres/schema.sql" >"$RUN_DIR/logs/postgres-schema.out"
  run_postgres_sql "$ROOT/fixtures/postgres/seed.sql" >"$RUN_DIR/logs/postgres-seed.out"
}

record_result() {
  local backend="$1" source="$2" status="$3" direct_file="$4" gateway_file="$5"
  python3 - "$RESULTS" "$backend" "$source" "$status" "$direct_file" "$gateway_file" <<'PY'
import json
import sys
from pathlib import Path

results, backend, source, status, direct_file, gateway_file = sys.argv[1:]
entry = {
    "backend": backend,
    "source": source,
    "status": status,
    "direct_output": direct_file,
    "gateway_output": gateway_file,
}
with open(results, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(entry, sort_keys=True) + "\n")
PY
}

run_comparison() {
  local backend="$1" source="$2" sql_file="$3" direct_output gateway_output
  direct_output="$RUN_DIR/normalized-output/${backend}-${source}-direct.tsv"
  gateway_output="$RUN_DIR/normalized-output/${backend}-${source}-gateway.tsv"
  local direct_raw="$RUN_DIR/logs/${backend}-${source}-direct.raw"
  local gateway_raw="$RUN_DIR/logs/${backend}-${source}-gateway.raw"

  echo "==> comparing $backend/$source"
  if [[ "$backend" == "mysql" ]]; then
    run_mysql_sql "$sql_file" >"$direct_raw" 2>"$direct_raw.err"
    run_mysql_gateway "$sql_file" >"$gateway_raw" 2>"$gateway_raw.err"
  else
    run_postgres_sql "$sql_file" >"$direct_raw" 2>"$direct_raw.err"
    run_postgres_gateway "$sql_file" >"$gateway_raw" 2>"$gateway_raw.err"
  fi
  python3 "$ROOT/normalize.py" "$direct_raw" "$direct_output"
  python3 "$ROOT/normalize.py" "$gateway_raw" "$gateway_output"
  if ! cmp -s "$direct_output" "$gateway_output"; then
    record_result "$backend" "$source" "mismatch" "$direct_output" "$gateway_output"
    diff -u "$direct_output" "$gateway_output" >"$RUN_DIR/logs/${backend}-${source}.diff" || true
    echo "oracle mismatch for $backend/$source; see $RUN_DIR/logs/${backend}-${source}.diff" >&2
    return 1
  fi
  record_result "$backend" "$source" "passed" "$direct_output" "$gateway_output"
}

run_mutation_comparison() {
  local backend="$1" source="$2" sql_file="$3" state_file="$4"
  local direct_output="$RUN_DIR/normalized-output/${backend}-${source}-direct.tsv"
  local gateway_output="$RUN_DIR/normalized-output/${backend}-${source}-gateway.tsv"
  local direct_raw="$RUN_DIR/logs/${backend}-${source}-direct.raw"
  local gateway_raw="$RUN_DIR/logs/${backend}-${source}-gateway.raw"
  local direct_exec="$RUN_DIR/logs/${backend}-${source}-direct-exec.raw"
  local gateway_exec="$RUN_DIR/logs/${backend}-${source}-gateway-exec.raw"
  local direct_state="$RUN_DIR/logs/${backend}-${source}-direct-state.raw"
  local gateway_state="$RUN_DIR/logs/${backend}-${source}-gateway-state.raw"

  echo "==> comparing mutation $backend/$source"
  load_fresh_fixtures
  if [[ "$backend" == "mysql" ]]; then
    run_mysql_sql "$sql_file" >"$direct_exec"
    run_mysql_sql "$state_file" >"$direct_state"
  else
    run_postgres_sql "$sql_file" >"$direct_exec"
    run_postgres_sql "$state_file" >"$direct_state"
  fi
  load_fresh_fixtures
  if [[ "$backend" == "mysql" ]]; then
    run_mysql_gateway "$sql_file" >"$gateway_exec"
    run_mysql_sql "$state_file" >"$gateway_state"
  else
    run_postgres_gateway "$sql_file" >"$gateway_exec"
    run_postgres_sql "$state_file" >"$gateway_state"
  fi
  { cat "$direct_exec"; printf '%s\n' '-- state --'; cat "$direct_state"; } >"$direct_raw"
  { cat "$gateway_exec"; printf '%s\n' '-- state --'; cat "$gateway_state"; } >"$gateway_raw"
  python3 "$ROOT/normalize.py" "$direct_raw" "$direct_output"
  python3 "$ROOT/normalize.py" "$gateway_raw" "$gateway_output"
  if ! cmp -s "$direct_output" "$gateway_output"; then
    record_result "$backend" "$source" "mismatch" "$direct_output" "$gateway_output"
    diff -u "$direct_output" "$gateway_output" >"$RUN_DIR/logs/${backend}-${source}.diff" || true
    echo "mutation oracle mismatch for $backend/$source" >&2
    return 1
  fi
  record_result "$backend" "$source" "passed" "$direct_output" "$gateway_output"
}

run_error_comparison() {
  local backend="$1" source="$2" sql_file="$3"
  local direct_output="$RUN_DIR/normalized-output/${backend}-${source}-direct.tsv"
  local gateway_output="$RUN_DIR/normalized-output/${backend}-${source}-gateway.tsv"
  local direct_raw="$RUN_DIR/logs/${backend}-${source}-direct.err"
  local gateway_raw="$RUN_DIR/logs/${backend}-${source}-gateway.err"

  echo "==> comparing error $backend/$source"
  load_fresh_fixtures
  if [[ "$backend" == "mysql" ]]; then
    run_mysql_sql "$sql_file" >"/dev/null" 2>"$direct_raw" && return 1
    run_mysql_gateway "$sql_file" >"/dev/null" 2>"$gateway_raw" && return 1
  else
    run_postgres_sql "$sql_file" >"/dev/null" 2>"$direct_raw" && return 1
    run_postgres_gateway "$sql_file" >"/dev/null" 2>"$gateway_raw" && return 1
  fi
  python3 "$ROOT/normalize.py" --error-dialect "$backend" "$direct_raw" "$direct_output"
  python3 "$ROOT/normalize.py" --error-dialect "$backend" "$gateway_raw" "$gateway_output"
  if ! cmp -s "$direct_output" "$gateway_output"; then
    record_result "$backend" "$source" "mismatch" "$direct_output" "$gateway_output"
    diff -u "$direct_output" "$gateway_output" >"$RUN_DIR/logs/${backend}-${source}.diff" || true
    echo "error oracle mismatch for $backend/$source" >&2
    return 1
  fi
  record_result "$backend" "$source" "passed" "$direct_output" "$gateway_output"
}

echo "==> loading versioned schema and seed"
load_fresh_fixtures

echo "==> preparing SQLT-2 gateway"
GATEWAY_BIN="$CARGO_TARGET_DIR/debug/proxy"
if [[ "${SQLT_FORCE_BUILD:-0}" == "1" || ! -x "$GATEWAY_BIN" ]]; then
  (
    cd "$PROJECT_ROOT"
    cargo build -p data-proxy --bin proxy
  ) >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" | tee "$RUN_DIR/logs/cargo-build.log"
fi
[[ -x "$GATEWAY_BIN" ]] || { echo "gateway binary not found: $GATEWAY_BIN" >&2; exit 1; }
python3 - "$RUN_DIR/run-metadata.json" "$PROJECT_ROOT" "$GATEWAY_BIN" \
  "$(rustc --version)" "mysql:8.0.42" "postgres:16.8" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path

output, project_root, binary, rustc_version, mysql_image, postgres_image = sys.argv[1:]
project_root_path = Path(project_root)
binary_path = Path(binary)

def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(project_root_path.parent), *args], text=True
    ).strip()

digest = hashlib.sha256()
with binary_path.open("rb") as handle:
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)

metadata = {
    "git_commit": git("rev-parse", "HEAD"),
    "git_dirty": bool(git("status", "--porcelain")),
    "gateway_binary": str(binary_path),
    "gateway_sha256": digest.hexdigest(),
    "rustc": rustc_version,
    "images": {"mysql": mysql_image, "postgres": postgres_image},
}
Path(output).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
"$GATEWAY_BIN" daemon -c "$GATEWAY_CONFIG" >"$GATEWAY_LOG" 2>&1 &
GATEWAY_PID=$!

for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:28082/admin/listeners >/dev/null 2>&1; then
    break
  fi
  if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
    echo "gateway exited early; see $GATEWAY_LOG" >&2
    exit 1
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json"

run_comparison mysql read "$ROOT/fixtures/mysql/oracle-read.sql"
run_comparison postgres read "$ROOT/fixtures/postgres/oracle-read.sql"
run_comparison mysql state "$ROOT/fixtures/mysql/oracle-state.sql"
run_comparison postgres state "$ROOT/fixtures/postgres/oracle-state.sql"
run_mutation_comparison mysql dml-tcl \
  "$ROOT/fixtures/mysql/oracle-dml-tcl.sql" \
  "$ROOT/fixtures/mysql/oracle-dml-tcl-state.sql"
run_mutation_comparison postgres dml-tcl \
  "$ROOT/fixtures/postgres/oracle-dml-tcl.sql" \
  "$ROOT/fixtures/postgres/oracle-dml-tcl-state.sql"
run_mutation_comparison mysql ddl \
  "$ROOT/fixtures/mysql/oracle-ddl.sql" \
  "$ROOT/fixtures/mysql/oracle-ddl-state.sql"
run_mutation_comparison postgres ddl \
  "$ROOT/fixtures/postgres/oracle-ddl.sql" \
  "$ROOT/fixtures/postgres/oracle-ddl-state.sql"
run_error_comparison mysql error "$ROOT/fixtures/mysql/oracle-error.sql"
run_error_comparison postgres error "$ROOT/fixtures/postgres/oracle-error.sql"

python3 - "$RESULTS" "$RUN_DIR/summary.txt" <<'PY'
import json
import sys
from pathlib import Path

results = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()]
failed = [item for item in results if item["status"] != "passed"]
summary = f"SQLT-2 backend oracle comparisons: {len(results)} passed, {len(failed)} failed.\n"
Path(sys.argv[2]).write_text(summary, encoding="utf-8")
if failed:
    raise SystemExit(summary)
print(summary, end="")
PY

echo "SQLT-2 fixture acceptance passed: $RUN_DIR"
