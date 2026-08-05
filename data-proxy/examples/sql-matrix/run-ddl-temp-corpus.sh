#!/usr/bin/env bash
# Verify temporary-table visibility and disconnect cleanup with real client sessions.
# All raw responses, normalized errors, and summaries stay in the external cache.
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
RUN_ID="${SQLT_DDL_TEMP_RUN_ID:-ddl-temp-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
SOURCES="${SQLT_DDL_TEMP_SOURCES:-direct gateway}"
COMPOSE_PROJECT="sqlt3dtemp-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
GATEWAY_CONFIG="$ROOT/fixtures/gateway-config.toml"
GATEWAY_PID=""
HOLDER_PID=""
HOLDER_OPEN=0
RESULTS="$RUN_DIR/results.jsonl"

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/normalized-output" "$RUN_DIR/fifos"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/ddl-temp-oracles.json" "$RUN_DIR/ddl-temp-oracles.json"

cleanup() {
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
[[ "$(rustc --version)" == rustc\ 1.94.1\ * ]] || {
  echo "SQLT-3D requires rustc 1.94.1; found: $(rustc --version)" >&2
  exit 1
}
python3 "$ROOT/validate.py"
for source in $SOURCES; do
  [[ "$source" == direct || "$source" == gateway ]] || {
    echo "unsupported SQLT_DDL_TEMP_SOURCES value: $source" >&2
    exit 1
  }
done

echo "==> starting fixed-version SQLT-3D temporary-table backends"
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
  echo "reusing cached gateway binary: $GATEWAY_BIN" >"$RUN_DIR/logs/cargo-build.log"
fi
[[ -x "$GATEWAY_BIN" ]] || { echo "gateway binary not found: $GATEWAY_BIN" >&2; exit 1; }
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

reset_case() {
  local dialect="$1"
  "${dialect}_direct" <"$ROOT/fixtures/$dialect/cleanup.sql" >/dev/null
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
  local dialect="$1" expected="$2" count
  for _ in $(seq 1 100); do
    count="$(transaction_count "$dialect" || true)"
    if [[ "$count" =~ ^[0-9]+$ ]] && (( count == expected )); then return 0; fi
    sleep 0.1
  done
  echo "timed out waiting for $dialect transaction count $expected; last: ${count:-unknown}" >&2
  return 1
}

wait_for_exit() {
  local pid="$1"
  for _ in $(seq 1 100); do
    if ! kill -0 "$pid" 2>/dev/null; then return 0; fi
    sleep 0.1
  done
  return 1
}

write_oracle_field() {
  python3 - "$ROOT/ddl-temp-oracles.json" "$1" "$2" "$3" "$4" <<'PY'
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
  local expected="$RUN_DIR/normalized-output/$prefix-$field.expected.tsv"
  write_oracle_field "$case_id" "$dialect" "$field" "$expected"
  if ! cmp -s "$expected" "$actual"; then
    diff -u "$expected" "$actual" >"$RUN_DIR/logs/$prefix-$field.diff" || true
    return 1
  fi
}

normalize_output() {
  python3 "$ROOT/normalize.py" "$1" "$2"
}

normalize_error() {
  python3 "$ROOT/normalize.py" --error-dialect "$1" "$2" "$3"
}

start_holder() {
  local dialect="$1" source="$2" sql_path="$3" prefix="$4"
  local fifo="$RUN_DIR/fifos/$prefix.fifo"
  HOLDER_RAW="$RUN_DIR/results/$prefix-holder.raw"
  HOLDER_ERR="$RUN_DIR/logs/$prefix-holder.err"
  rm -f "$fifo"
  mkfifo "$fifo"
  exec 9<>"$fifo"
  HOLDER_OPEN=1
  (exec 9>&-; run_client "$dialect" "$source") <"$fifo" >"$HOLDER_RAW" 2>"$HOLDER_ERR" &
  HOLDER_PID=$!
  printf '%s\n' "START TRANSACTION;" >&9
  sed -n '1,$p' "$sql_path" >&9
  printf '%s\n' \
    "INSERT INTO sqlt_ddl_temp (probe_id, probe_name) VALUES (10, 'ten'), (20, 'twenty');" \
    "SELECT 'SQLT_TEMP', COUNT(*), SUM(probe_id) FROM sqlt_ddl_temp;" >&9
  wait_for_transaction_count "$dialect" 1 || {
    sed -n '1,120p' "$HOLDER_ERR" >&2 || true
    return 1
  }
}

release_holder() {
  local dialect="$1"
  printf '%s\n' "ROLLBACK;" >&9
  exec 9>&-
  HOLDER_OPEN=0
  if ! wait_for_exit "$HOLDER_PID"; then
    echo "temporary-table holder did not exit: $HOLDER_PID" >&2
    return 1
  fi
  wait "$HOLDER_PID"
  HOLDER_PID=""
  wait_for_transaction_count "$dialect" 0
}

probe_missing() {
  local dialect="$1" source="$2" prefix="$3"
  PROBE_RAW="$RUN_DIR/results/$prefix.raw"
  PROBE_ERR="$RUN_DIR/logs/$prefix.err"
  if printf '%s\n' 'SELECT COUNT(*) FROM sqlt_ddl_temp;' | \
    run_client "$dialect" "$source" >"$PROBE_RAW" 2>"$PROBE_ERR"; then
    echo "temporary table unexpectedly visible: $prefix" >&2
    return 1
  fi
}

write_result() {
  python3 - "$RESULTS" "$@" <<'PY'
import json
import sys
from pathlib import Path

results, case_id, dialect, source, status, holder, isolated, disconnected = sys.argv[1:]
with Path(results).open("a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "case_id": case_id,
        "dialect": dialect,
        "source": source,
        "status": status,
        "holder_output": holder,
        "isolated_error": isolated,
        "after_disconnect_error": disconnected,
    }, sort_keys=True) + "\n")
PY
}

case_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  for source in $SOURCES; do
    case_count=$((case_count + 1))
    prefix="$case_id-$dialect-$source"
    echo "==> $case_id [$dialect/$source]"
    reset_case "$dialect"
    status=passed
    start_holder "$dialect" "$source" "$ROOT/cases/$sql_file" "$prefix" || status=failed

    holder_normalized="$RUN_DIR/normalized-output/$prefix-same-session.tsv"
    isolated_normalized="$RUN_DIR/normalized-output/$prefix-isolated-error.tsv"
    disconnected_normalized="$RUN_DIR/normalized-output/$prefix-after-disconnect-error.tsv"
    if [[ "$status" == passed ]]; then
      probe_missing "$dialect" "$source" "$prefix-isolated" || status=failed
      if ! normalize_error "$dialect" "$PROBE_ERR" "$isolated_normalized" || \
        ! compare_field "$case_id" "$dialect" isolated_session_error "$isolated_normalized" "$prefix"; then
        status=failed
      fi
    fi
    release_holder "$dialect" || status=failed
    normalize_output "$HOLDER_RAW" "$holder_normalized"
    if ! compare_field "$case_id" "$dialect" same_session "$holder_normalized" "$prefix"; then
      status=failed
    fi
    if ! probe_missing "$dialect" "$source" "$prefix-after-disconnect" || \
      ! normalize_error "$dialect" "$PROBE_ERR" "$disconnected_normalized" || \
      ! compare_field "$case_id" "$dialect" after_disconnect_error "$disconnected_normalized" "$prefix"; then
      status=failed
    fi

    if [[ "$status" == passed ]]; then
      pass_count=$((pass_count + 1))
    else
      fail_count=$((fail_count + 1))
    fi
    write_result "$case_id" "$dialect" "$source" "$status" \
      "$holder_normalized" "$isolated_normalized" "$disconnected_normalized"
  done
done < <(python3 - "$ROOT/manifest.json" <<'PY'
import json
import sys

for case in json.load(open(sys.argv[1], encoding="utf-8"))["cases"]:
    if case.get("capability") != "ddl.temporary_table":
        continue
    for dialect in case["dialects"]:
        print(case["id"], dialect, case["sql_file"], sep="\t")
PY
)

python3 - "$RESULTS" "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" <<'PY'
import json
import sys
from pathlib import Path

results_path, output, case_count, pass_count, fail_count = sys.argv[1:]
results = [json.loads(line) for line in Path(results_path).read_text(encoding="utf-8").splitlines()]
summary = {
    "executions": int(case_count),
    "passed": int(pass_count),
    "failed": int(fail_count),
    "results": results,
}
Path(output).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if summary["failed"]:
    raise SystemExit(f"SQLT-3D temporary tables failed: {summary['passed']} passed, {summary['failed']} failed")
print(f"SQLT-3D temporary tables passed: {summary['passed']} case/dialect/source executions")
PY

echo "artifacts: $RUN_DIR"
