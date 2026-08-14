#!/usr/bin/env bash
# Execute the registered SQLT-3C DML corpus against fixed Docker backends.
# Each case is reset before direct and gateway execution; all artifacts stay external.
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
RUN_ID="${SQLT_DML_RUN_ID:-dml-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
CASE_FROM="${SQLT_DML_CASE_FROM:-SQLT-DML-003}"
CASE_TO="${SQLT_DML_CASE_TO:-SQLT-DML-043}"
COMPOSE_PROJECT="sqlt3cdml-${RUN_ID//[^a-zA-Z0-9]/}"
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
cp "$ROOT/dml-oracles.json" "$RUN_DIR/dml-oracles.json"

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
  echo "SQLT-3C requires rustc 1.94.1; found: $(rustc --version)" >&2
  exit 1
}
python3 "$ROOT/validate.py"
python3 "$ROOT/select_dml_cases.py" "$ROOT/manifest.json" \
  "$ROOT/dml-oracles.json" "$CASE_FROM" "$CASE_TO" >"$RUN_DIR/selection.tsv"
[[ -s "$RUN_DIR/selection.tsv" ]] || { echo "DML case selection is empty" >&2; exit 1; }

echo "==> starting fixed-version SQLT-3C Docker backends"
"${COMPOSE[@]}" up -d >"$RUN_DIR/logs/compose-up.log" 2>&1
for _ in $(seq 1 90); do
  mysql_ok="$("${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null || true)"
  pg_ok="$("${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt 2>/dev/null || true)"
  if [[ "$mysql_ok" == *"mysqld is alive"* && "$pg_ok" == *"accepting connections"* ]]; then break; fi
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

run_mysql_exec() {
  "${COMPOSE[@]}" exec -T mysql mysql --default-character-set=utf8mb4 \
    --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt -vvv <"$1"
}

run_postgres_exec() {
  "${COMPOSE[@]}" exec -T postgres psql -X -v ON_ERROR_STOP=1 \
    -v VERBOSITY=verbose -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt <"$1"
}

run_mysql_gateway() {
  docker run --rm "${RUN_LABEL[@]}" -i --add-host=host.docker.internal:host-gateway mysql:8.0.42 \
    mysql --default-character-set=utf8mb4 --ssl-mode=DISABLED -vvv \
    -h host.docker.internal -P 29088 -uroot -proot <"$1"
}

run_postgres_gateway() {
  docker run --rm "${RUN_LABEL[@]}" -i --add-host=host.docker.internal:host-gateway postgres:16.8 \
    env PGPASSWORD=root psql -X -v ON_ERROR_STOP=1 -v VERBOSITY=verbose \
    -P null=NULL -A -t -F $'\t' -h host.docker.internal -p 29089 -U root -d sqlt <"$1"
}

run_mysql_transaction_exec() {
  local force_flag="${2:-}"
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names $force_flag \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$1"
}

run_mysql_transaction_gateway() {
  local force_flag="${2:-}"
  docker run --rm "${RUN_LABEL[@]}" -i --add-host=host.docker.internal:host-gateway mysql:8.0.42 \
    mysql --batch --raw --skip-column-names $force_flag --default-character-set=utf8mb4 \
    --ssl-mode=DISABLED -h host.docker.internal -P 29088 -uroot -proot <"$1"
}

run_postgres_transaction_exec() {
  local stop_on_error="$2"
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v "ON_ERROR_STOP=$stop_on_error" \
    -v VERBOSITY=verbose -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt <"$1"
}

run_postgres_transaction_gateway() {
  local stop_on_error="$2"
  docker run --rm "${RUN_LABEL[@]}" -i --add-host=host.docker.internal:host-gateway postgres:16.8 \
    env PGPASSWORD=root psql -X -q -v "ON_ERROR_STOP=$stop_on_error" -v VERBOSITY=verbose \
    -P null=NULL -A -t -F $'\t' -h host.docker.internal -p 29089 -U root -d sqlt <"$1"
}

load_fixtures() {
  local dialect="$1"
  if [[ "$dialect" == "mysql" ]]; then
    run_mysql "$ROOT/fixtures/mysql/cleanup.sql" >"$RUN_DIR/logs/mysql-cleanup.out"
    run_mysql "$ROOT/fixtures/mysql/schema.sql" >"$RUN_DIR/logs/mysql-schema.out"
    run_mysql "$ROOT/fixtures/mysql/seed.sql" >"$RUN_DIR/logs/mysql-seed.out"
  else
    run_postgres "$ROOT/fixtures/postgres/cleanup.sql" >"$RUN_DIR/logs/postgres-cleanup.out"
    run_postgres "$ROOT/fixtures/postgres/schema.sql" >"$RUN_DIR/logs/postgres-schema.out"
    run_postgres "$ROOT/fixtures/postgres/seed.sql" >"$RUN_DIR/logs/postgres-seed.out"
  fi
}

write_result() {
  python3 - "$RESULTS" "$@" <<'PY'
import json
import sys
from pathlib import Path

(
    results, case_id, dialect, status, source, execution, direct_state, gateway_state,
    direct_affected, gateway_affected, direct_returned, gateway_returned,
    direct_transaction, gateway_transaction,
) = sys.argv[1:]
with Path(results).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "case_id": case_id,
        "dialect": dialect,
        "status": status,
        "source": source,
        "execution": execution,
        "direct_state": direct_state,
        "gateway_state": gateway_state,
        "direct_affected_rows": direct_affected,
        "gateway_affected_rows": gateway_affected,
        "direct_returned_rows": direct_returned,
        "gateway_returned_rows": gateway_returned,
        "direct_transaction_markers": direct_transaction,
        "gateway_transaction_markers": gateway_transaction,
    }, sort_keys=True) + "\n")
PY
}

normalize_state() {
  python3 "$ROOT/normalize.py" "$1" "$2"
}

normalize_error() {
  python3 "$ROOT/normalize.py" --error-dialect "$1" "$2" "$3"
}

normalize_affected() {
  python3 "$ROOT/normalize.py" --affected-dialect "$1" "$2" "$3"
}

normalize_returned() {
  python3 "$ROOT/normalize.py" --returned-dialect "$1" "$2" "$3"
}

normalize_transaction() {
  python3 "$ROOT/normalize.py" --transaction-markers "$1" "$2"
}

case_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  case_count=$((case_count + 1))
  sql_path="$ROOT/cases/$sql_file"
  oracle="$RUN_DIR/results/${case_id}-${dialect}.oracle.json"
  python3 - "$ROOT/dml-oracles.json" "$case_id" "$dialect" "$oracle" <<'PY'
import json
import sys
from pathlib import Path

source, case_id, dialect, destination = sys.argv[1:]
value = json.load(open(source, encoding="utf-8"))["results"][case_id][dialect]
Path(destination).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  expected_result="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["result"])' "$oracle")"
  expected_state="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-state.tsv"
  expected_error="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-error.tsv"
  expected_affected="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-affected.tsv"
  expected_returned="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-returned.tsv"
  expected_transaction="$RUN_DIR/normalized-output/${case_id}-${dialect}.expected-transaction.tsv"
  empty_state="$RUN_DIR/normalized-output/${case_id}-${dialect}.empty-state.tsv"
  : >"$empty_state"
  python3 - "$oracle" "$expected_state" "$expected_error" "$expected_affected" "$expected_returned" "$expected_transaction" <<'PY'
import json
import sys
from pathlib import Path

value = json.load(open(sys.argv[1], encoding="utf-8"))
Path(sys.argv[2]).write_text(value.get("state", ""), encoding="utf-8")
Path(sys.argv[3]).write_text(value.get("error", ""), encoding="utf-8")
Path(sys.argv[4]).write_text(
    "" if "affected_rows" not in value else str(value["affected_rows"]) + "\n",
    encoding="utf-8",
)
Path(sys.argv[5]).write_text(value.get("returned_rows", ""), encoding="utf-8")
Path(sys.argv[6]).write_text(value.get("transaction_markers", ""), encoding="utf-8")
PY
  has_affected="$(python3 -c 'import json,sys; print("yes" if "affected_rows" in json.load(open(sys.argv[1])) else "no")' "$oracle")"
  has_returned="$(python3 -c 'import json,sys; print("yes" if "returned_rows" in json.load(open(sys.argv[1])) else "no")' "$oracle")"
  has_transaction="$(python3 -c 'import json,sys; print("yes" if "transaction_markers" in json.load(open(sys.argv[1])) else "no")' "$oracle")"
  state_query_group="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["state_query"])' "$oracle")"
  echo "==> $case_id [$dialect]"
  case_status=passed
  direct_affected_file=""
  gateway_affected_file=""
  direct_returned_file=""
  gateway_returned_file=""
  direct_transaction_file=""
  gateway_transaction_file=""
  for path in direct gateway; do
    load_fixtures "$dialect"
    prefix="$RUN_DIR/results/${case_id}-${dialect}-${path}"
    pre_raw="$prefix-pre.raw"
    post_raw="$prefix-post.raw"
    pre_state="$prefix-pre.tsv"
    post_state="$prefix-post.tsv"
    exec_raw="$prefix-exec.raw"
    actual_affected="$prefix-affected.tsv"
    actual_returned="$prefix-returned.tsv"
    actual_transaction="$prefix-transaction.tsv"
    err_raw="$RUN_DIR/logs/${case_id}-${dialect}-${path}.err"
    exec_status=0
    if [[ "$dialect" == "mysql" ]]; then
      state_query_relative="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["state_queries"][sys.argv[2]][sys.argv[3]])' "$ROOT/dml-oracles.json" "$state_query_group" "$dialect")"
      state_query="$ROOT/$state_query_relative"
      run_mysql "$state_query" >"$pre_raw"
      if [[ "$has_transaction" == yes ]]; then
        force_flag=""
        [[ "$expected_result" == recovered_error ]] && force_flag="--force"
        if [[ "$path" == direct ]]; then run_mysql_transaction_exec "$sql_path" "$force_flag" >"$exec_raw" 2>"$err_raw" || exec_status=$?;
        else run_mysql_transaction_gateway "$sql_path" "$force_flag" >"$exec_raw" 2>"$err_raw" || exec_status=$?; fi
      elif [[ "$path" == direct ]]; then run_mysql_exec "$sql_path" >"$exec_raw" 2>"$err_raw" || exec_status=$?;
      else run_mysql_gateway "$sql_path" >"$exec_raw" 2>"$err_raw" || exec_status=$?; fi
      run_mysql "$state_query" >"$post_raw"
    else
      state_query_relative="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["state_queries"][sys.argv[2]][sys.argv[3]])' "$ROOT/dml-oracles.json" "$state_query_group" "$dialect")"
      state_query="$ROOT/$state_query_relative"
      run_postgres "$state_query" >"$pre_raw"
      if [[ "$has_transaction" == yes ]]; then
        stop_on_error=1
        [[ "$expected_result" == recovered_error ]] && stop_on_error=0
        if [[ "$path" == direct ]]; then run_postgres_transaction_exec "$sql_path" "$stop_on_error" >"$exec_raw" 2>"$err_raw" || exec_status=$?;
        else run_postgres_transaction_gateway "$sql_path" "$stop_on_error" >"$exec_raw" 2>"$err_raw" || exec_status=$?; fi
      elif [[ "$path" == direct ]]; then run_postgres_exec "$sql_path" >"$exec_raw" 2>"$err_raw" || exec_status=$?;
      else run_postgres_gateway "$sql_path" >"$exec_raw" 2>"$err_raw" || exec_status=$?; fi
      run_postgres "$state_query" >"$post_raw"
    fi
    normalize_state "$pre_raw" "$pre_state"
    normalize_state "$post_raw" "$post_state"
    if [[ "$expected_result" == success || "$expected_result" == recovered_error ]]; then
      if [[ "$has_affected" == yes ]]; then
        normalize_affected "$dialect" "$exec_raw" "$actual_affected" || exec_status=$?
        if [[ "$path" == direct ]]; then direct_affected_file="$actual_affected"; else gateway_affected_file="$actual_affected"; fi
      fi
      if [[ "$has_returned" == yes ]]; then
        normalize_returned "$dialect" "$exec_raw" "$actual_returned" || exec_status=$?
        if [[ "$path" == direct ]]; then direct_returned_file="$actual_returned"; else gateway_returned_file="$actual_returned"; fi
      fi
      if [[ "$has_transaction" == yes ]]; then
        normalize_transaction "$exec_raw" "$actual_transaction" || exec_status=$?
        if [[ "$path" == direct ]]; then direct_transaction_file="$actual_transaction"; else gateway_transaction_file="$actual_transaction"; fi
      fi
      if [[ "$expected_result" == recovered_error ]]; then
        actual_error="$RUN_DIR/normalized-output/${case_id}-${dialect}-${path}.error.tsv"
        : >"$actual_error"
        normalize_error "$dialect" "$err_raw" "$actual_error" || exec_status=$?
      fi
      if [[ "$exec_status" -ne 0 ]] || ! cmp -s "$expected_state" "$post_state" || \
        { [[ "$has_affected" == yes ]] && ! cmp -s "$expected_affected" "$actual_affected"; } || \
        { [[ "$has_returned" == yes ]] && ! cmp -s "$expected_returned" "$actual_returned"; } || \
        { [[ "$has_transaction" == yes ]] && ! cmp -s "$expected_transaction" "$actual_transaction"; } || \
        { [[ "$expected_result" == recovered_error ]] && ! cmp -s "$expected_error" "$actual_error"; } || \
        { [[ "$case_id" < "SQLT-DML-015" ]] && ! cmp -s "$pre_state" "$empty_state"; }; then
        case_status=failed
      fi
    else
      actual_error="$RUN_DIR/normalized-output/${case_id}-${dialect}-${path}.error.tsv"
      : >"$actual_error"
      if [[ "$exec_status" -eq 0 ]]; then
        case_status=failed
      elif ! normalize_error "$dialect" "$err_raw" "$actual_error"; then
        case_status=failed
      fi
      if [[ "$exec_status" -eq 0 ]] || ! cmp -s "$expected_error" "$actual_error" || ! cmp -s "$pre_state" "$post_state"; then
        case_status=failed
      fi
    fi
    if [[ "$case_status" != passed ]]; then
      diff -u "$expected_state" "$post_state" >"$RUN_DIR/logs/${case_id}-${dialect}-${path}.state.diff" || true
      if [[ "$expected_result" == error || "$expected_result" == recovered_error ]]; then
        diff -u "$expected_error" "$actual_error" >"$RUN_DIR/logs/${case_id}-${dialect}-${path}.error.diff" || true
      fi
      if [[ "$has_affected" == yes && -f "$actual_affected" ]]; then
        diff -u "$expected_affected" "$actual_affected" >"$RUN_DIR/logs/${case_id}-${dialect}-${path}.affected.diff" || true
      fi
      if [[ "$has_returned" == yes && -f "$actual_returned" ]]; then
        diff -u "$expected_returned" "$actual_returned" >"$RUN_DIR/logs/${case_id}-${dialect}-${path}.returned.diff" || true
      fi
      if [[ "$has_transaction" == yes && -f "$actual_transaction" ]]; then
        diff -u "$expected_transaction" "$actual_transaction" >"$RUN_DIR/logs/${case_id}-${dialect}-${path}.transaction.diff" || true
      fi
    fi
  done
  write_result "$case_id" "$dialect" "$case_status" "$sql_file" "$expected_result" \
    "$RUN_DIR/results/${case_id}-${dialect}-direct-post.tsv" \
    "$RUN_DIR/results/${case_id}-${dialect}-gateway-post.tsv" \
    "$direct_affected_file" "$gateway_affected_file" \
    "$direct_returned_file" "$gateway_returned_file" \
    "$direct_transaction_file" "$gateway_transaction_file"
  if [[ "$case_status" == passed ]]; then pass_count=$((pass_count + 1)); else fail_count=$((fail_count + 1)); fi
done <"$RUN_DIR/selection.tsv"

python3 - "$RESULTS" "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" <<'PY'
import json
import sys
from pathlib import Path

results_path, output, case_count, pass_count, fail_count = sys.argv[1:]
results = [json.loads(line) for line in Path(results_path).read_text(encoding="utf-8").splitlines()]
summary = {
    "cases": int(case_count),
    "passed": int(pass_count),
    "failed": int(fail_count),
    "results": results,
}
Path(output).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if summary["failed"]:
    raise SystemExit(f"SQLT-3C failed: {summary['passed']} passed, {summary['failed']} failed")
print(f"SQLT-3C passed: {summary['passed']} case/dialect executions")
PY
