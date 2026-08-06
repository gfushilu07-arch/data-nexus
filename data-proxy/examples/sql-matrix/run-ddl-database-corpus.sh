#!/usr/bin/env bash
# Verify MySQL database DDL privilege boundaries through direct and gateway paths.
# Root only prepares and observes state; every case statement runs as the sqlt account.
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
RUN_ID="${SQLT_DDL_DATABASE_RUN_ID:-ddl-database-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
COMPOSE_PROJECT="sqlt3ddatabase-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
ORACLES="$ROOT/ddl-database-oracles.json"
RESULTS="$RUN_DIR/results.jsonl"
GATEWAY_CONFIG="$ROOT/fixtures/gateway-config.toml"
GATEWAY_LOG="$RUN_DIR/logs/gateway.log"
GATEWAY_PID=""
GATEWAY_CLIENT="${COMPOSE_PROJECT}-gateway-client"

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/normalized-output" "$RUN_DIR/results"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ORACLES" "$RUN_DIR/ddl-database-oracles.json"

run_mysql_root() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot <"$1"
}

cleanup() {
  docker rm -f "$GATEWAY_CLIENT" >/dev/null 2>&1 || true
  if "${COMPOSE[@]}" ps --status running mysql 2>/dev/null | grep -q mysql; then
    run_mysql_root "$ROOT/fixtures/mysql/ddl-database-cleanup.sql" >/dev/null 2>&1 || true
  fi
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || { echo "missing required command: docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing required command: python3" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "missing required command: curl" >&2; exit 1; }
[[ "$(rustc --version)" == rustc\ 1.94.1\ * ]] || {
  echo "SQLT-3D requires rustc 1.94.1; found: $(rustc --version)" >&2
  exit 1
}
python3 "$ROOT/validate.py"

echo "==> starting fixed-version MySQL 8.0.42 backend"
"${COMPOSE[@]}" up -d mysql >"$RUN_DIR/logs/compose-up.log" 2>&1
for _ in $(seq 1 90); do
  mysql_ok="$("${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null || true)"
  if [[ "$mysql_ok" == *"mysqld is alive"* ]]; then break; fi
  sleep 2
done
"${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent
"${COMPOSE[@]}" exec -T mysql mysql --batch --skip-column-names -uroot -proot \
  -e 'SELECT VERSION(); SHOW GRANTS FOR CURRENT_USER();' >"$RUN_DIR/logs/mysql-version-and-root-grants.txt"
"${COMPOSE[@]}" exec -T mysql mysql --batch --skip-column-names -usqlt -psqlt \
  -e 'SHOW GRANTS FOR CURRENT_USER();' >"$RUN_DIR/logs/sqlt-grants.txt"

echo "==> preparing security-off gateway"
GATEWAY_BIN="$CARGO_TARGET_DIR/debug/proxy"
if [[ "${SQLT_FORCE_BUILD:-0}" == "1" || ! -x "$GATEWAY_BIN" ]]; then
  (cd "$PROJECT_ROOT" && cargo build -p data-proxy --bin proxy) \
    >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" | tee "$RUN_DIR/logs/cargo-build.log"
fi
[[ -x "$GATEWAY_BIN" ]] || { echo "gateway binary not found: $GATEWAY_BIN" >&2; exit 1; }
"$GATEWAY_BIN" daemon -c "$GATEWAY_CONFIG" >"$GATEWAY_LOG" 2>&1 &
GATEWAY_PID=$!
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json" 2>/dev/null; then
    break
  fi
  if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
    echo "gateway exited early; see $GATEWAY_LOG" >&2
    exit 1
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json"

run_mysql_direct() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --connect-timeout=10 --default-character-set=utf8mb4 --protocol=TCP \
    -h 127.0.0.1 -usqlt -psqlt sqlt <"$1"
}

run_mysql_gateway() {
  docker rm -f "$GATEWAY_CLIENT" >/dev/null 2>&1 || true
  docker run --name "$GATEWAY_CLIENT" --rm -i \
    --add-host=host.docker.internal:host-gateway mysql:8.0.42 \
    mysql --batch --raw --skip-column-names --default-character-set=utf8mb4 \
    --connect-timeout=10 --ssl-mode=DISABLED \
    -h host.docker.internal -P 29088 -uroot -proot <"$1" &
  local client_pid=$!
  for _ in $(seq 1 30); do
    if ! kill -0 "$client_pid" 2>/dev/null; then
      wait "$client_pid"
      return $?
    fi
    sleep 1
  done
  echo "gateway MySQL client timed out after 30 seconds" >&2
  docker rm -f "$GATEWAY_CLIENT" >/dev/null 2>&1 || true
  kill "$client_pid" 2>/dev/null || true
  wait "$client_pid" 2>/dev/null || true
  return 124
}

oracle_path() {
  python3 - "$ORACLES" "$1" <<'PY'
import json
import sys

print(json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]])
PY
}

normalize_output() {
  local source="$1"
  local destination="$2"
  python3 "$ROOT/normalize.py" "$source" "$destination"
}

snapshot_root() {
  local destination="$1"
  local query
  query="$(oracle_path catalog_query)"
  run_mysql_root "$ROOT/$query" >"$destination"
  normalize_output "$destination" "$destination.normalized"
  mv "$destination.normalized" "$destination"
}

snapshot_restricted() {
  local destination="$1"
  local query
  query="$(oracle_path restricted_catalog_query)"
  run_mysql_direct "$ROOT/$query" >"$destination"
  normalize_output "$destination" "$destination.normalized"
  mv "$destination.normalized" "$destination"
}

snapshot_identity() {
  local path="$1"
  local destination="$2"
  local query
  query="$(oracle_path identity_query)"
  if [[ "$path" == direct ]]; then
    run_mysql_direct "$ROOT/$query" >"$destination"
  else
    run_mysql_gateway "$ROOT/$query" >"$destination"
  fi
  normalize_output "$destination" "$destination.normalized"
  mv "$destination.normalized" "$destination"
}

write_result() {
  python3 - "$RESULTS" "$@" <<'PY'
import json
import sys
from pathlib import Path

(
    results, case_id, path, status, execution, before_root, after_root,
    before_restricted, after_restricted, identity, error,
) = sys.argv[1:]
with Path(results).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "case_id": case_id,
        "dialect": "mysql",
        "path": path,
        "status": status,
        "execution": execution,
        "before_root_catalog": before_root,
        "after_root_catalog": after_root,
        "before_restricted_catalog": before_restricted,
        "after_restricted_catalog": after_restricted,
        "identity": identity,
        "error": error,
    }, sort_keys=True) + "\n")
PY
}

case_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  [[ "$dialect" == mysql ]] || { echo "unexpected D3d dialect: $dialect" >&2; exit 1; }
  sql_path="$ROOT/cases/$sql_file"
  oracle="$RUN_DIR/results/${case_id}-${dialect}.oracle.json"
  python3 - "$ORACLES" "$case_id" "$dialect" "$oracle" <<'PY'
import json
import sys
from pathlib import Path

source, case_id, dialect, destination = sys.argv[1:]
value = json.load(open(source, encoding="utf-8"))["results"][case_id][dialect]
Path(destination).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  setup="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["setup"])' "$oracle")"
  unchanged="$(python3 -c 'import json,sys; print("yes" if json.load(open(sys.argv[1]))["unchanged"] else "no")' "$oracle")"
  expected_error="$RUN_DIR/normalized-output/${case_id}-mysql.expected-error.tsv"
  expected_root="$RUN_DIR/normalized-output/${case_id}-mysql.expected-root.tsv"
  expected_restricted="$RUN_DIR/normalized-output/${case_id}-mysql.expected-restricted.tsv"
  expected_identity="$RUN_DIR/normalized-output/${case_id}-mysql.expected-identity.tsv"
  python3 - "$oracle" "$expected_error" "$expected_root" "$expected_restricted" "$expected_identity" <<'PY'
import json
import sys
from pathlib import Path

value = json.load(open(sys.argv[1], encoding="utf-8"))
for destination, field in zip(sys.argv[2:], ("error", "root_state", "restricted_state", "identity")):
    Path(destination).write_text(value[field], encoding="utf-8")
PY

  for path in direct gateway; do
    case_count=$((case_count + 1))
    echo "==> $case_id [mysql/$path]"
    run_mysql_root "$ROOT/fixtures/mysql/ddl-database-cleanup.sql" >/dev/null
    run_mysql_root "$ROOT/$setup" >/dev/null

    prefix="$RUN_DIR/results/${case_id}-mysql-${path}"
    before_root="$prefix-before-root.tsv"
    after_root="$prefix-after-root.tsv"
    before_restricted="$prefix-before-restricted.tsv"
    after_restricted="$prefix-after-restricted.tsv"
    identity="$prefix-identity.tsv"
    stdout="$prefix.stdout"
    stderr="$prefix.stderr"
    actual_error="$RUN_DIR/normalized-output/${case_id}-mysql-${path}.error.tsv"

    snapshot_root "$before_root"
    snapshot_restricted "$before_restricted"
    snapshot_identity "$path" "$identity"
    exec_status=0
    if [[ "$path" == direct ]]; then
      run_mysql_direct "$sql_path" >"$stdout" 2>"$stderr" || exec_status=$?
    else
      run_mysql_gateway "$sql_path" >"$stdout" 2>"$stderr" || exec_status=$?
    fi
    snapshot_root "$after_root"
    snapshot_restricted "$after_restricted"

    status=passed
    if [[ "$exec_status" -eq 0 ]] || \
      ! python3 "$ROOT/normalize.py" --error-dialect mysql "$stderr" "$actual_error" || \
      ! cmp -s "$expected_error" "$actual_error" || \
      ! cmp -s "$expected_root" "$after_root" || \
      ! cmp -s "$expected_restricted" "$after_restricted" || \
      ! cmp -s "$expected_identity" "$identity"; then
      status=failed
    fi
    if [[ "$unchanged" == yes ]] && { ! cmp -s "$before_root" "$after_root" || ! cmp -s "$before_restricted" "$after_restricted"; }; then
      status=failed
    fi

    execution="error:$exec_status"
    write_result "$case_id" "$path" "$status" "$execution" \
      "$before_root" "$after_root" "$before_restricted" "$after_restricted" "$identity" "$actual_error"
    if [[ "$status" == passed ]]; then
      pass_count=$((pass_count + 1))
    else
      fail_count=$((fail_count + 1))
      echo "FAILED: inspect $prefix* and $actual_error" >&2
      diff -u "$expected_error" "$actual_error" || true
      diff -u "$expected_root" "$after_root" || true
      diff -u "$expected_restricted" "$after_restricted" || true
      diff -u "$expected_identity" "$identity" || true
      diff -u "$before_root" "$after_root" || true
      diff -u "$before_restricted" "$after_restricted" || true
    fi
  done
done < <(python3 "$ROOT/select_ddl_database_cases.py" "$ROOT/manifest.json" "$ORACLES")

python3 - "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" <<'PY'
import json
import sys
from pathlib import Path

destination, total, passed, failed = sys.argv[1:]
Path(destination).write_text(json.dumps({
    "suite": "SQLT-3D3d",
    "total": int(total),
    "passed": int(passed),
    "failed": int(failed),
}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

echo "SQLT-3D3d summary: total=$case_count passed=$pass_count failed=$fail_count"
echo "Artifacts: $RUN_DIR"
[[ "$fail_count" -eq 0 ]]
