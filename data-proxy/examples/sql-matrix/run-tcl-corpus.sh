#!/usr/bin/env bash
# Execute the explicit TCL corpus against fixed Docker backends and the local gateway.
# Each direct and gateway path starts from a clean fixture; all artifacts stay external.
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
RUN_ID="${SQLT_TCL_RUN_ID:-tcl-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
CASE_FROM="${SQLT_TCL_CASE_FROM:-SQLT-TCL-001}"
CASE_TO="${SQLT_TCL_CASE_TO:-SQLT-TCL-011}"
COMPOSE_PROJECT="sqlt3etcl-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
RESULTS="$RUN_DIR/results.jsonl"
GATEWAY_CONFIG="$ROOT/fixtures/gateway-config.toml"
GATEWAY_LOG="$RUN_DIR/logs/gateway.log"
GATEWAY_PID=""
RUN_LABEL=(--label "data-nexus.sql-matrix.run-id=$RUN_ID")

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/normalized-output" "$RUN_DIR/results"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/tcl-oracles.json" "$RUN_DIR/tcl-oracles.json"

cleanup() {
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
  echo "SQLT-3E1 requires rustc 1.94.1; found: $(rustc --version)" >&2
  exit 1
}
python3 "$ROOT/validate.py"
python3 "$ROOT/select_tcl_cases.py" "$ROOT/manifest.json" \
  "$ROOT/tcl-oracles.json" "$CASE_FROM" "$CASE_TO" >"$RUN_DIR/selection.tsv"
[[ -s "$RUN_DIR/selection.tsv" ]] || { echo "TCL case selection is empty" >&2; exit 1; }

echo "==> starting fixed-version SQLT-3E1 Docker backends"
"${COMPOSE[@]}" up -d >"$RUN_DIR/logs/compose-up.log" 2>&1
for _ in $(seq 1 90); do
  mysql_ok="$("${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null || true)"
  pg_ok="$("${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt 2>/dev/null || true)"
  if [[ "$mysql_ok" == *"mysqld is alive"* && "$pg_ok" == *"accepting connections"* ]]; then
    break
  fi
  sleep 2
done
"${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent
"${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt

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
printf '%s\n' "$GATEWAY_PID" >"$RUN_DIR/gateway.pid"
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

run_mysql() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$1"
}

run_postgres() {
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 \
    -v VERBOSITY=verbose -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt <"$1"
}

run_mysql_case() {
  local path="$1"
  local sql="$2"
  local result="$3"
  local force_flag=""
  [[ "$result" == recovered_error ]] && force_flag="--force"
  if [[ "$path" == direct ]]; then
    "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names $force_flag \
      --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$sql"
  else
    docker run --rm "${RUN_LABEL[@]}" -i --add-host=host.docker.internal:host-gateway mysql:8.0.42 \
      mysql --batch --raw --skip-column-names $force_flag --default-character-set=utf8mb4 \
      --ssl-mode=DISABLED -h host.docker.internal -P 29088 -uroot -proot <"$sql"
  fi
}

run_postgres_case() {
  local path="$1"
  local sql="$2"
  local result="$3"
  local stop=1
  [[ "$result" == recovered_error ]] && stop=0
  if [[ "$path" == direct ]]; then
    "${COMPOSE[@]}" exec -T postgres psql -X -q -v "ON_ERROR_STOP=$stop" \
      -v VERBOSITY=verbose -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt <"$sql"
  else
    docker run --rm "${RUN_LABEL[@]}" -i --add-host=host.docker.internal:host-gateway postgres:16.8 \
      env PGPASSWORD=root psql -X -q -v "ON_ERROR_STOP=$stop" -v VERBOSITY=verbose \
      -P null=NULL -A -t -F $'\t' -h host.docker.internal -p 29089 -U root -d sqlt <"$sql"
  fi
}

load_fixtures() {
  local dialect="$1"
  local label="$2"
  if [[ "$dialect" == mysql ]]; then
    run_mysql "$ROOT/fixtures/mysql/cleanup.sql" >"$RUN_DIR/logs/${label}-cleanup.out"
    run_mysql "$ROOT/fixtures/mysql/schema.sql" >"$RUN_DIR/logs/${label}-schema.out"
    run_mysql "$ROOT/fixtures/mysql/seed.sql" >"$RUN_DIR/logs/${label}-seed.out"
  else
    run_postgres "$ROOT/fixtures/postgres/cleanup.sql" >"$RUN_DIR/logs/${label}-cleanup.out"
    run_postgres "$ROOT/fixtures/postgres/schema.sql" >"$RUN_DIR/logs/${label}-schema.out"
    run_postgres "$ROOT/fixtures/postgres/seed.sql" >"$RUN_DIR/logs/${label}-seed.out"
  fi
}

write_result() {
  python3 - "$RESULTS" "$@" <<'PY'
import json
import sys
from pathlib import Path

results, case_id, dialect, status, source, execution, direct_state, gateway_state, direct_markers, gateway_markers, direct_error, gateway_error = sys.argv[1:]
with Path(results).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "case_id": case_id,
        "dialect": dialect,
        "status": status,
        "source": source,
        "execution": execution,
        "direct_state": direct_state,
        "gateway_state": gateway_state,
        "direct_transaction_markers": direct_markers,
        "gateway_transaction_markers": gateway_markers,
        "direct_error": direct_error,
        "gateway_error": gateway_error,
    }, sort_keys=True) + "\n")
PY
}

case_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  case_count=$((case_count + 1))
  sql_path="$ROOT/cases/$sql_file"
  oracle="$RUN_DIR/results/${case_id}-${dialect}.oracle.json"
  python3 - "$ROOT/tcl-oracles.json" "$case_id" "$dialect" "$oracle" <<'PY'
import json
import sys
from pathlib import Path

source, case_id, dialect, destination = sys.argv[1:]
value = json.load(open(source, encoding="utf-8"))["results"][case_id][dialect]
Path(destination).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  expected_result="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["result"])' "$oracle")"
  state_group="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["state_query"])' "$oracle")"
  state_query_relative="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["state_queries"][sys.argv[2]][sys.argv[3]])' "$ROOT/tcl-oracles.json" "$state_group" "$dialect")"
  state_query="$ROOT/$state_query_relative"
  expected_state="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-state.tsv"
  expected_markers="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-markers.tsv"
  expected_error="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-error.tsv"
  python3 - "$oracle" "$expected_state" "$expected_markers" "$expected_error" <<'PY'
import json
import sys
from pathlib import Path

value = json.load(open(sys.argv[1], encoding="utf-8"))
Path(sys.argv[2]).write_text(value["state"], encoding="utf-8")
Path(sys.argv[3]).write_text(value["transaction_markers"], encoding="utf-8")
Path(sys.argv[4]).write_text(value.get("error", ""), encoding="utf-8")
PY
  echo "==> $case_id [$dialect]"
  case_status=passed
  direct_state=""
  gateway_state=""
  direct_markers=""
  gateway_markers=""
  direct_error=""
  gateway_error=""
  for path in direct gateway; do
    label="${case_id}-${dialect}-${path}"
    load_fixtures "$dialect" "$label"
    exec_raw="$RUN_DIR/results/${label}-exec.raw"
    err_raw="$RUN_DIR/logs/${label}.err"
    actual_state="$RUN_DIR/results/${label}-state.tsv"
    actual_markers="$RUN_DIR/results/${label}-markers.tsv"
    actual_error="$RUN_DIR/results/${label}-error.tsv"
    : >"$exec_raw"
    : >"$err_raw"
    : >"$actual_error"
    exec_status=0
    if [[ "$dialect" == mysql ]]; then
      run_mysql_case "$path" "$sql_path" "$expected_result" >"$exec_raw" 2>"$err_raw" || exec_status=$?
      run_mysql "$state_query" | python3 "$ROOT/normalize.py" /dev/stdin "$actual_state"
    else
      run_postgres_case "$path" "$sql_path" "$expected_result" >"$exec_raw" 2>"$err_raw" || exec_status=$?
      run_postgres "$state_query" | python3 "$ROOT/normalize.py" /dev/stdin "$actual_state"
    fi
    python3 "$ROOT/normalize.py" --transaction-markers "$exec_raw" "$actual_markers" || exec_status=$?
    if [[ "$expected_result" == recovered_error ]]; then
      python3 "$ROOT/normalize.py" --error-dialect "$dialect" "$err_raw" "$actual_error" || exec_status=$?
    fi
    if [[ "$exec_status" -ne 0 ]] || ! cmp -s "$expected_state" "$actual_state" || \
      ! cmp -s "$expected_markers" "$actual_markers" || ! cmp -s "$expected_error" "$actual_error"; then
      case_status=failed
      diff -u "$expected_state" "$actual_state" >"$RUN_DIR/logs/${label}.state.diff" || true
      diff -u "$expected_markers" "$actual_markers" >"$RUN_DIR/logs/${label}.markers.diff" || true
      diff -u "$expected_error" "$actual_error" >"$RUN_DIR/logs/${label}.error.diff" || true
    fi
    if [[ "$path" == direct ]]; then
      direct_state="$actual_state"
      direct_markers="$actual_markers"
      direct_error="$actual_error"
    else
      gateway_state="$actual_state"
      gateway_markers="$actual_markers"
      gateway_error="$actual_error"
    fi
  done
  write_result "$case_id" "$dialect" "$case_status" "$sql_file" "$expected_result" \
    "$direct_state" "$gateway_state" "$direct_markers" "$gateway_markers" \
    "$direct_error" "$gateway_error"
  if [[ "$case_status" == passed ]]; then
    pass_count=$((pass_count + 1))
  else
    fail_count=$((fail_count + 1))
  fi
done <"$RUN_DIR/selection.tsv"

python3 - "$RESULTS" "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" <<'PY'
import json
import sys
from pathlib import Path

results_path, output, case_count, pass_count, fail_count = sys.argv[1:]
results = [json.loads(line) for line in Path(results_path).read_text(encoding="utf-8").splitlines()]
summary = {
    "case_dialect_executions": int(case_count),
    "path_executions": int(case_count) * 2,
    "passed": int(pass_count),
    "failed": int(fail_count),
    "results": results,
}
Path(output).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if summary["failed"]:
    raise SystemExit(f"SQLT-3E1 failed: {summary['passed']} passed, {summary['failed']} failed")
print(f"SQLT-3E1 passed: {summary['passed']} case/dialect and {summary['path_executions']} path executions")
PY
