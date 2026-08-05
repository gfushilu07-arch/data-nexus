#!/usr/bin/env bash
# Verify large DQL outputs through streaming summaries on direct and gateway paths.
# Raw results and all derived artifacts stay in the external Data Nexus cache.
set -euo pipefail

RUST_TOOLCHAIN_BIN="${RUST_TOOLCHAIN_BIN:-/Volumes/fushilu/.rustup/toolchains/1.94.1-aarch64-apple-darwin/bin}"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$RUST_TOOLCHAIN_BIN:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"
export CARGO_TARGET_DIR="${DATA_NEXUS_CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.94.1}"

ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT/../.." && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_DQL_BOUNDARY_RUN_ID:-dql-boundary-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
CASE_FROM="${SQLT_DQL_BOUNDARY_CASE_FROM:-SQLT-DQL-085}"
CASE_TO="${SQLT_DQL_BOUNDARY_CASE_TO:-SQLT-DQL-086}"
SOURCES="${SQLT_DQL_BOUNDARY_SOURCES:-direct gateway}"
COMPOSE_PROJECT="sqlt3b4boundary-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
GATEWAY_CONFIG="$ROOT/fixtures/gateway-config.toml"
GATEWAY_PID=""
RESULTS="$RUN_DIR/results.jsonl"

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/summaries"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/dql-boundary-oracles.json" "$RUN_DIR/dql-boundary-oracles.json"
CHUNK_BYTES="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["chunk_bytes"])' \
  "$ROOT/dql-boundary-oracles.json")"

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
python3 "$ROOT/validate.py"
for source in $SOURCES; do
  [[ "$source" == direct || "$source" == gateway ]] || {
    echo "unsupported SQLT_DQL_BOUNDARY_SOURCES value: $source" >&2
    exit 1
  }
done

echo "==> starting fixed-version SQLT-3B4 boundary backends"
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

write_expected() {
  python3 - "$ROOT/dql-boundary-oracles.json" "$1" "$2" "$3" <<'PY'
import json
import sys
from pathlib import Path

source, case_id, dialect, destination = sys.argv[1:]
value = json.load(open(source, encoding="utf-8"))["results"][case_id][dialect]
Path(destination).write_text(
    json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
}

write_result() {
  python3 - "$RESULTS" "$@" <<'PY'
import json
import sys

results, case_id, dialect, source, status, raw, summary, expected = sys.argv[1:]
with open(results, "a", encoding="utf-8") as handle:
    handle.write(json.dumps({
        "case_id": case_id,
        "dialect": dialect,
        "source": source,
        "status": status,
        "raw_output": raw,
        "actual_summary": summary,
        "expected_summary": expected,
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
    prefix="${case_id}-${dialect}-${source}"
    raw="$RUN_DIR/results/$prefix.raw"
    err="$RUN_DIR/logs/$prefix.err"
    actual="$RUN_DIR/summaries/$prefix.actual.json"
    expected="$RUN_DIR/summaries/$prefix.expected.json"
    sql_path="$ROOT/cases/$sql_file"
    echo "==> $case_id [$dialect/$source]"
    status=passed
    if ! run_client "$dialect" "$source" <"$sql_path" >"$raw" 2>"$err"; then
      status=failed
    else
      python3 "$ROOT/stream_summary.py" --chunk-bytes "$CHUNK_BYTES" "$raw" "$actual"
      write_expected "$case_id" "$dialect" "$expected"
      if ! cmp -s "$expected" "$actual"; then
        status=mismatch
        diff -u "$expected" "$actual" >"$RUN_DIR/logs/$prefix.diff" || true
      fi
    fi
    if [[ "$status" == passed ]]; then
      pass_count=$((pass_count + 1))
    else
      fail_count=$((fail_count + 1))
      sed -n '1,100p' "$err" >&2 || true
      sed -n '1,120p' "$RUN_DIR/logs/$prefix.diff" >&2 2>/dev/null || true
    fi
    write_result "$case_id" "$dialect" "$source" "$status" "$raw" "$actual" "$expected"
  done
done < <(python3 - "$ROOT/manifest.json" "$CASE_FROM" "$CASE_TO" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
case_from, case_to = sys.argv[2:]
for case in manifest["cases"]:
    if case["capability"] != "dql.boundary" or not case_from <= case["id"] <= case_to:
        continue
    for dialect in case["dialects"]:
        print(f'{case["id"]}\t{dialect}\t{case["sql_file"]}')
PY
)

python3 - "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" "$RUN_DIR" <<'PY'
import json
import sys
from pathlib import Path

summary, total, passed, failed, run_dir = sys.argv[1:]
Path(summary).write_text(json.dumps({
    "suite": "SQLT-3B4-DQL-BOUNDARY",
    "total": int(total),
    "passed": int(passed),
    "failed": int(failed),
    "run_dir": run_dir,
}, indent=2) + "\n", encoding="utf-8")
PY

echo "SQLT-3B4 DQL boundary corpus: $pass_count/$case_count passed"
[[ "$case_count" -gt 0 && "$fail_count" == 0 ]]
