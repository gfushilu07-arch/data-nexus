#!/usr/bin/env bash
# Verify SQLT-3B4 row-lock semantics with two real direct or gateway connections.
# Raw responses and structured results stay in the external Data Nexus cache.
set -euo pipefail

RUST_TOOLCHAIN_BIN="${RUST_TOOLCHAIN_BIN:-/Volumes/fushilu/.rustup/toolchains/1.94.1-aarch64-apple-darwin/bin}"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$RUST_TOOLCHAIN_BIN:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"
export CARGO_TARGET_DIR="${DATA_NEXUS_CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.94.1}"

ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT/../.." && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_DQL_LOCK_RUN_ID:-dql-lock-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
CASE_FROM="${SQLT_DQL_LOCK_CASE_FROM:-SQLT-DQL-081}"
CASE_TO="${SQLT_DQL_LOCK_CASE_TO:-SQLT-DQL-084}"
SOURCES="${SQLT_DQL_LOCK_SOURCES:-direct gateway}"
COMPOSE_PROJECT="sqlt3b4lock-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
GATEWAY_CONFIG="$ROOT/fixtures/gateway-config.toml"
GATEWAY_PID=""
HOLDER_PID=""
CONTENDER_PID=""
HOLDER_OPEN=0
RESULTS="$RUN_DIR/results.jsonl"

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/normalized-output" "$RUN_DIR/fifos"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/dql-lock-oracles.json" "$RUN_DIR/dql-lock-oracles.json"

cleanup() {
  if [[ -n "$CONTENDER_PID" ]] && kill -0 "$CONTENDER_PID" 2>/dev/null; then
    kill "$CONTENDER_PID" 2>/dev/null || true
    wait "$CONTENDER_PID" 2>/dev/null || true
  fi
  if [[ "$HOLDER_OPEN" == 1 ]]; then
    printf '%s\n' "ROLLBACK;" >&9 2>/dev/null || true
    exec 9>&- 2>/dev/null || true
    HOLDER_OPEN=0
  fi
  if [[ -n "$HOLDER_PID" ]] && kill -0 "$HOLDER_PID" 2>/dev/null; then
    kill "$HOLDER_PID" 2>/dev/null || true
    wait "$HOLDER_PID" 2>/dev/null || true
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
python3 "$ROOT/validate.py"
for source in $SOURCES; do
  [[ "$source" == direct || "$source" == gateway ]] || {
    echo "unsupported SQLT_DQL_LOCK_SOURCES value: $source" >&2
    exit 1
  }
done

echo "==> starting fixed-version SQLT-3B4 Docker backends"
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
  [[ "$(rustc --version)" == rustc\ 1.94.1\ * ]] || {
    echo "SQLT-3B4 requires rustc 1.94.1; found: $(rustc --version)" >&2
    exit 1
  }
  (cd "$PROJECT_ROOT" && cargo build -p data-proxy --bin proxy) \
    >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" >"$RUN_DIR/logs/cargo-build.log"
fi
"$GATEWAY_BIN" daemon -c "$GATEWAY_CONFIG" >"$RUN_DIR/logs/gateway.log" 2>&1 &
GATEWAY_PID=$!
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json" 2>/dev/null; then
    break
  fi
  kill -0 "$GATEWAY_PID" 2>/dev/null || {
    echo "gateway exited early; see $RUN_DIR/logs/gateway.log" >&2
    exit 1
  }
  sleep 1
done
curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json"

mysql_direct() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt
}

postgres_direct() {
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 \
    -v VERBOSITY=verbose -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt
}

mysql_gateway() {
  docker run --rm -i --add-host=host.docker.internal:host-gateway mysql:8.0.42 \
    mysql --batch --raw --skip-column-names --default-character-set=utf8mb4 \
    --ssl-mode=DISABLED -h host.docker.internal -P 29088 -uroot -proot sqlt
}

postgres_gateway() {
  docker run --rm -i --add-host=host.docker.internal:host-gateway postgres:16.8 \
    env PGPASSWORD=root psql -X -q -v ON_ERROR_STOP=1 -v VERBOSITY=verbose \
    -P null=NULL -A -t -F $'\t' -h host.docker.internal -p 29089 -U root -d sqlt
}

run_client() {
  local dialect="$1" source="$2"
  "${dialect}_${source}"
}

load_fixtures() {
  local dialect="$1"
  if [[ "$dialect" == mysql ]]; then
    mysql_direct <"$ROOT/fixtures/mysql/cleanup.sql" >/dev/null
    mysql_direct <"$ROOT/fixtures/mysql/schema.sql" >/dev/null
    mysql_direct <"$ROOT/fixtures/mysql/seed.sql" >/dev/null
  else
    postgres_direct <"$ROOT/fixtures/postgres/cleanup.sql" >/dev/null
    postgres_direct <"$ROOT/fixtures/postgres/schema.sql" >/dev/null
    postgres_direct <"$ROOT/fixtures/postgres/seed.sql" >/dev/null
  fi
}

transaction_count() {
  local dialect="$1" value
  if [[ "$dialect" == mysql ]]; then
    value="$(printf '%s\n' 'SELECT COUNT(*) FROM information_schema.innodb_trx;' | mysql_direct 2>/dev/null)"
  else
    value="$(printf '%s\n' "SELECT COUNT(*) FROM pg_stat_activity WHERE datname = 'sqlt' AND state = 'idle in transaction';" | postgres_direct 2>/dev/null)"
  fi
  printf '%s\n' "$value" | tail -n 1
}

wait_for_transaction_count() {
  local dialect="$1" expected="$2" attempts="${3:-100}" count
  for _ in $(seq 1 "$attempts"); do
    count="$(transaction_count "$dialect" || true)"
    if [[ "$count" =~ ^[0-9]+$ ]] && (( count == expected )); then
      return 0
    fi
    sleep 0.1
  done
  echo "timed out waiting for $dialect transaction count $expected; last count: ${count:-unknown}" >&2
  return 1
}

wait_for_exit() {
  local pid="$1" attempts="${2:-100}"
  for _ in $(seq 1 "$attempts"); do
    if ! kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
    sleep 0.1
  done
  return 1
}

start_holder() {
  local dialect="$1" source="$2" mode="$3" prefix="$4"
  HOLDER_FIFO="$RUN_DIR/fifos/$prefix.fifo"
  HOLDER_RAW="$RUN_DIR/results/$prefix-holder.raw"
  HOLDER_ERR="$RUN_DIR/logs/$prefix-holder.err"
  rm -f "$HOLDER_FIFO"
  mkfifo "$HOLDER_FIFO"
  exec 9<>"$HOLDER_FIFO"
  HOLDER_OPEN=1
  (exec 9>&-; run_client "$dialect" "$source") \
    <"$HOLDER_FIFO" >"$HOLDER_RAW" 2>"$HOLDER_ERR" &
  HOLDER_PID=$!
  sed -n '1,$p' "$ROOT/fixtures/$dialect/lock-holder-$mode.sql" >&9
  wait_for_transaction_count "$dialect" 1 || {
    sed -n '1,120p' "$HOLDER_ERR" >&2 || true
    return 1
  }
}

release_holder() {
  local dialect="$1"
  printf '%s\n' "ROLLBACK;" "SELECT 'SQLT_HOLDER_ROLLED_BACK';" >&9
  exec 9>&-
  HOLDER_OPEN=0
  if ! wait_for_exit "$HOLDER_PID" 100; then
    echo "holder did not exit after rollback: $HOLDER_PID" >&2
    return 1
  fi
  wait "$HOLDER_PID"
  HOLDER_PID=""
  grep -Fxq 'SQLT_HOLDER_ROLLED_BACK' "$HOLDER_RAW" || {
    echo "holder rollback marker missing: $HOLDER_RAW" >&2
    return 1
  }
  wait_for_transaction_count "$dialect" 0
}

normalize_output() {
  python3 "$ROOT/normalize.py" "$1" "$2"
}

normalize_error() {
  python3 "$ROOT/normalize.py" --error-dialect "$1" "$2" "$3"
}

write_oracle_field() {
  python3 - "$ROOT/dql-lock-oracles.json" "$1" "$2" "$3" "$4" <<'PY'
import json
import sys
from pathlib import Path

source, case_id, dialect, field, destination = sys.argv[1:]
contract = json.load(open(source, encoding="utf-8"))["results"][case_id][dialect]
Path(destination).write_text(contract[field], encoding="utf-8")
PY
}

compare_field() {
  local case_id="$1" dialect="$2" field="$3" actual="$4" prefix="$5"
  local expected="$RUN_DIR/normalized-output/$prefix-$field.expected.txt"
  write_oracle_field "$case_id" "$dialect" "$field" "$expected"
  if ! cmp -s "$expected" "$actual"; then
    diff -u "$expected" "$actual" >"$RUN_DIR/logs/$prefix-$field.diff" || true
    return 1
  fi
}

run_query() {
  local dialect="$1" source="$2" sql_path="$3" prefix="$4"
  QUERY_RAW="$RUN_DIR/results/$prefix.raw"
  QUERY_ERR="$RUN_DIR/logs/$prefix.err"
  if run_client "$dialect" "$source" <"$sql_path" >"$QUERY_RAW" 2>"$QUERY_ERR"; then
    QUERY_STATUS=0
  else
    QUERY_STATUS=$?
  fi
}

verify_recovery() {
  local case_id="$1" dialect="$2" source="$3" sql_path="$4" prefix="$5"
  local normalized="$RUN_DIR/normalized-output/$prefix-recovery.txt"
  run_query "$dialect" "$source" "$sql_path" "$prefix-recovery"
  [[ "$QUERY_STATUS" == 0 ]] || return 1
  normalize_output "$QUERY_RAW" "$normalized"
  compare_field "$case_id" "$dialect" after_rollback "$normalized" "$prefix"
}

check_block_then_complete() {
  local case_id="$1" dialect="$2" source="$3" sql_path="$4" prefix="$5"
  local raw="$RUN_DIR/results/$prefix-contender.raw"
  local err="$RUN_DIR/logs/$prefix-contender.err"
  local normalized="$RUN_DIR/normalized-output/$prefix-after-rollback.txt"
  local empty="$RUN_DIR/normalized-output/$prefix-during-lock.txt"

  start_holder "$dialect" "$source" update "$prefix"
  run_client "$dialect" "$source" <"$sql_path" >"$raw" 2>"$err" &
  CONTENDER_PID=$!
  sleep 1
  if ! kill -0 "$CONTENDER_PID" 2>/dev/null; then
    echo "contender returned before holder rollback" >&2
    return 1
  fi
  normalize_output "$raw" "$empty"
  compare_field "$case_id" "$dialect" during_lock "$empty" "$prefix"
  release_holder "$dialect"
  wait_for_exit "$CONTENDER_PID" 100 || return 1
  wait "$CONTENDER_PID"
  CONTENDER_PID=""
  normalize_output "$raw" "$normalized"
  compare_field "$case_id" "$dialect" after_rollback "$normalized" "$prefix"
  verify_recovery "$case_id" "$dialect" "$source" "$sql_path" "$prefix"
}

check_shared_compatible() {
  local case_id="$1" dialect="$2" source="$3" sql_path="$4" prefix="$5"
  local normalized="$RUN_DIR/normalized-output/$prefix-during-lock.txt"
  local error="$RUN_DIR/normalized-output/$prefix-conflict-error.txt"

  start_holder "$dialect" "$source" share "$prefix"
  run_query "$dialect" "$source" "$sql_path" "$prefix-shared-contender"
  [[ "$QUERY_STATUS" == 0 ]] || return 1
  normalize_output "$QUERY_RAW" "$normalized"
  compare_field "$case_id" "$dialect" during_lock "$normalized" "$prefix"
  run_query "$dialect" "$source" "$ROOT/cases/dql/for-update-nowait.sql" "$prefix-update-probe"
  [[ "$QUERY_STATUS" != 0 ]] || {
    echo "FOR UPDATE NOWAIT unexpectedly acquired a share-locked row" >&2
    return 1
  }
  normalize_error "$dialect" "$QUERY_ERR" "$error"
  compare_field "$case_id" "$dialect" conflict_error "$error" "$prefix"
  release_holder "$dialect"
  verify_recovery "$case_id" "$dialect" "$source" "$sql_path" "$prefix"
}

check_fail_nowait() {
  local case_id="$1" dialect="$2" source="$3" sql_path="$4" prefix="$5"
  local error="$RUN_DIR/normalized-output/$prefix-during-lock-error.txt"

  start_holder "$dialect" "$source" update "$prefix"
  run_query "$dialect" "$source" "$sql_path" "$prefix-contender"
  [[ "$QUERY_STATUS" != 0 ]] || {
    echo "NOWAIT unexpectedly acquired an update-locked row" >&2
    return 1
  }
  normalize_error "$dialect" "$QUERY_ERR" "$error"
  compare_field "$case_id" "$dialect" during_lock_error "$error" "$prefix"
  release_holder "$dialect"
  verify_recovery "$case_id" "$dialect" "$source" "$sql_path" "$prefix"
}

check_skip_locked() {
  local case_id="$1" dialect="$2" source="$3" sql_path="$4" prefix="$5"
  local normalized="$RUN_DIR/normalized-output/$prefix-during-lock.txt"

  start_holder "$dialect" "$source" update "$prefix"
  run_query "$dialect" "$source" "$sql_path" "$prefix-contender"
  [[ "$QUERY_STATUS" == 0 ]] || return 1
  normalize_output "$QUERY_RAW" "$normalized"
  compare_field "$case_id" "$dialect" during_lock "$normalized" "$prefix"
  release_holder "$dialect"
  verify_recovery "$case_id" "$dialect" "$source" "$sql_path" "$prefix"
}

force_release_holder() {
  if [[ "$HOLDER_OPEN" == 1 ]]; then
    printf '%s\n' "ROLLBACK;" >&9 2>/dev/null || true
    exec 9>&- 2>/dev/null || true
    HOLDER_OPEN=0
  fi
  if [[ -n "${HOLDER_PID:-}" ]] && kill -0 "$HOLDER_PID" 2>/dev/null; then
    wait_for_exit "$HOLDER_PID" 30 || kill "$HOLDER_PID" 2>/dev/null || true
    wait "$HOLDER_PID" 2>/dev/null || true
  fi
  HOLDER_PID=""
  if [[ -n "$CONTENDER_PID" ]] && kill -0 "$CONTENDER_PID" 2>/dev/null; then
    wait_for_exit "$CONTENDER_PID" 30 || kill "$CONTENDER_PID" 2>/dev/null || true
    wait "$CONTENDER_PID" 2>/dev/null || true
  fi
  CONTENDER_PID=""
}

write_result() {
  python3 - "$RESULTS" "$@" <<'PY'
import json
import sys

results, case_id, dialect, source, behavior, status, prefix = sys.argv[1:]
with open(results, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "case_id": case_id,
        "dialect": dialect,
        "source": source,
        "behavior": behavior,
        "status": status,
        "artifact_prefix": prefix,
    }, sort_keys=True) + "\n")
PY
}

case_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file behavior; do
  [[ -n "$case_id" ]] || continue
  for source in $SOURCES; do
    case_count=$((case_count + 1))
    prefix="${case_id}-${dialect}-${source}"
    sql_path="$ROOT/cases/$sql_file"
    load_fixtures "$dialect"
    echo "==> $case_id [$dialect/$source] $behavior"
    status=passed
    if ! "check_${behavior}" "$case_id" "$dialect" "$source" "$sql_path" "$prefix"; then
      status=failed
      force_release_holder
      fail_count=$((fail_count + 1))
      echo "FAILED: $case_id [$dialect/$source]; see $RUN_DIR" >&2
      sed -n '1,100p' "$RUN_DIR/logs/$prefix"*.err >&2 2>/dev/null || true
      sed -n '1,120p' "$RUN_DIR/logs/$prefix"*.diff >&2 2>/dev/null || true
    else
      pass_count=$((pass_count + 1))
    fi
    write_result "$case_id" "$dialect" "$source" "$behavior" "$status" "$prefix"
  done
done < <(python3 - "$ROOT/manifest.json" "$ROOT/dql-lock-oracles.json" "$CASE_FROM" "$CASE_TO" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
oracles = json.load(open(sys.argv[2], encoding="utf-8"))["results"]
case_from, case_to = sys.argv[3:]
for case in manifest["cases"]:
    if (
        case["family"] != "dql"
        or case["transaction_mode"] != "explicit"
        or not case_from <= case["id"] <= case_to
    ):
        continue
    for dialect in case["dialects"]:
        behavior = oracles[case["id"]][dialect]["behavior"]
        print(f'{case["id"]}\t{dialect}\t{case["sql_file"]}\t{behavior}')
PY
)

python3 - "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" "$RUN_DIR" <<'PY'
import json
import sys
from pathlib import Path

summary, total, passed, failed, run_dir = sys.argv[1:]
Path(summary).write_text(json.dumps({
    "suite": "SQLT-3B4-DQL-LOCK",
    "total": int(total),
    "passed": int(passed),
    "failed": int(failed),
    "run_dir": run_dir,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "SQLT-3B4 DQL lock corpus: $pass_count/$case_count passed"
[[ "$case_count" -gt 0 && "$fail_count" == 0 ]]
