#!/usr/bin/env bash
# Execute MySQL binary prepared cases with a real connector in Docker.
set -euo pipefail

export PATH="/Applications/Docker.app/Contents/Resources/bin:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"
export CARGO_TARGET_DIR="${DATA_NEXUS_CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.94.1}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT/../.." && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_PREPARED_RUN_ID:-prepared-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
CASE_FROM="${SQLT_PREPARED_CASE_FROM:-SQLT-PRP-001}"
CASE_TO="${SQLT_PREPARED_CASE_TO:-SQLT-PRP-008}"
COMPOSE_PROJECT="sqlt3eprep-${RUN_ID//[^a-zA-Z0-9]/}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
RESULTS="$RUN_DIR/results.jsonl"
GATEWAY_PID=""
RUN_LABEL=(--label "data-nexus.sql-matrix.run-id=$RUN_ID")
CLIENT_IMAGE="${SQLT_PREPARED_CLIENT_IMAGE:-sqlt-prepared-client:9.4.0}"

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/normalized-output"
: >"$RESULTS"
cp "$ROOT/manifest.json" "$RUN_DIR/manifest.json"
cp "$ROOT/capabilities.json" "$RUN_DIR/capabilities.json"
cp "$ROOT/prepared-oracles.json" "$RUN_DIR/prepared-oracles.json"

cleanup() {
  [[ -z "$GATEWAY_PID" ]] || { kill "$GATEWAY_PID" 2>/dev/null || true; wait "$GATEWAY_PID" 2>/dev/null || true; }
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

command -v docker >/dev/null 2>&1 || { echo "missing docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing python3" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "missing curl" >&2; exit 1; }
command -v rustup >/dev/null 2>&1 || { echo "missing rustup" >&2; exit 1; }
[[ "$(rustup run "$RUSTUP_TOOLCHAIN" rustc --version)" == rustc\ 1.94.1\ * ]] || { echo "SQLT-3E2 requires rustc 1.94.1" >&2; exit 1; }
python3 "$ROOT/validate.py"
python3 "$ROOT/select_prepared_cases.py" "$ROOT/manifest.json" \
  "$ROOT/prepared-oracles.json" "$CASE_FROM" "$CASE_TO" >"$RUN_DIR/selection.tsv"
[[ -s "$RUN_DIR/selection.tsv" ]] || { echo "prepared case selection is empty" >&2; exit 1; }

docker build --pull=false -t "$CLIENT_IMAGE" -f - . >"$RUN_DIR/logs/client-image-build.log" 2>&1 <<'DOCKERFILE'
FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir --disable-pip-version-check "mysql-connector-python==9.4.0"
DOCKERFILE

"${COMPOSE[@]}" up -d >"$RUN_DIR/logs/compose-up.log" 2>&1
for _ in $(seq 1 90); do
  ping="$("${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null || true)"
  [[ "$ping" == *"mysqld is alive"* ]] && break
  sleep 2
done
"${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent

GATEWAY_BIN="$CARGO_TARGET_DIR/debug/proxy"
if [[ "${SQLT_FORCE_BUILD:-0}" == 1 || ! -x "$GATEWAY_BIN" ]]; then
  (cd "$PROJECT_ROOT" && rustup run "$RUSTUP_TOOLCHAIN" cargo build -p data-proxy --bin proxy) >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" | tee "$RUN_DIR/logs/cargo-build.log"
fi
"$GATEWAY_BIN" daemon -c "$ROOT/fixtures/gateway-config.toml" >"$RUN_DIR/logs/gateway.log" 2>&1 & GATEWAY_PID=$!
printf '%s\n' "$GATEWAY_PID" >"$RUN_DIR/gateway.pid"
for _ in $(seq 1 90); do
  curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json" 2>/dev/null && break
  if [[ -n "$GATEWAY_PID" ]] && ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
    echo "gateway exited early; see $RUN_DIR/logs/gateway.log" >&2
    exit 1
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:28082/admin/listeners >"$RUN_DIR/logs/listeners.json"

run_root() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$1"
}

load_fixture() {
  run_root "$ROOT/fixtures/mysql/cleanup.sql" >"$RUN_DIR/logs/fixture-cleanup.out"
  run_root "$ROOT/fixtures/mysql/schema.sql" >"$RUN_DIR/logs/fixture-schema.out"
  run_root "$ROOT/fixtures/mysql/seed.sql" >"$RUN_DIR/logs/fixture-seed.out"
}

run_client() {
  local path="$1" case_id="$2" sql_rel="$3" oracle_rel="$4" output="$5" control_rel="${6:-}"
  local port=23306 user=sqlt password=sqlt
  [[ "$path" == gateway ]] && { port=29088; user=root; password=root; }
  local client_args=(--case-id "$case_id" --sql "/matrix/$sql_rel" --oracle "/run/$oracle_rel" --host host.docker.internal --port "$port" --user "$user" --password "$password")
  if [[ -n "$control_rel" ]]; then
    client_args+=(--control-sql "/matrix/$control_rel" --control-port 23306)
  fi
  docker run --rm "${RUN_LABEL[@]}" --add-host=host.docker.internal:host-gateway \
    -v "$ROOT:/matrix:ro" -v "$RUN_DIR:/run:ro" \
    "$CLIENT_IMAGE" python /matrix/prepared_client.py "${client_args[@]}" \
    >"$output" 2>"${output%.json}.err"
}

case_count=0
pass_count=0
fail_count=0
while IFS=$'\t' read -r case_id dialect sql_file; do
  [[ -n "$case_id" ]] || continue
  case_count=$((case_count + 1))
  oracle_case="$RUN_DIR/results/${case_id}.oracle.json"
  python3 - "$ROOT/prepared-oracles.json" "$case_id" "$oracle_case" <<'PY'
import json, sys
from pathlib import Path
value = json.load(open(sys.argv[1], encoding="utf-8"))["results"][sys.argv[2]]
Path(sys.argv[3]).write_text(json.dumps(value) + "\n", encoding="utf-8")
PY
  expected="$RUN_DIR/normalized-output/${case_id}.expected.json"
  python3 - "$oracle_case" "$expected" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[2]).write_text(json.dumps(json.load(open(sys.argv[1]))["expected"], sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
PY
  control_sql="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("control_sql", ""))' "$oracle_case")"
  echo "==> $case_id [$dialect/direct + gateway]"
  status=passed
  for path in direct gateway; do
    label="${case_id}-${path}"
    # Rebuild every path so a direct schema mutation cannot leak into gateway.
    load_fixture
    if [[ "$case_id" == SQLT-PRP-008 ]]; then
      run_root "$ROOT/fixtures/mysql/prepared-schema-setup.sql" \
        >"$RUN_DIR/logs/${label}.prepared-schema-setup.out"
    fi
    actual="$RUN_DIR/results/${label}.json"
    run_client "$path" "$case_id" "cases/$sql_file" "results/${case_id}.oracle.json" "$actual" "$control_sql" || status=failed
    if [[ -s "$actual" ]]; then
      python3 - "$actual" "$expected" <<'PY' || status=failed
import json, sys
if json.load(open(sys.argv[1])) != json.load(open(sys.argv[2])):
    raise SystemExit(1)
PY
    else
      status=failed
    fi
    state_raw="$RUN_DIR/results/${label}.state.raw"
    run_root "$ROOT/fixtures/mysql/oracle-prepared-state.sql" >"$state_raw"
    python3 "$ROOT/normalize.py" "$state_raw" "$RUN_DIR/results/${label}.state.tsv"
    expected_state="$RUN_DIR/normalized-output/${case_id}.expected-state.tsv"
    python3 - "$oracle_case" "$expected_state" <<'PY'
import json, sys
from pathlib import Path
Path(sys.argv[2]).write_text(json.load(open(sys.argv[1]))["state"], encoding="utf-8")
PY
    cmp -s "$expected_state" "$RUN_DIR/results/${label}.state.tsv" || status=failed
  done
  printf '{"case_id":"%s","status":"%s"}\n' "$case_id" "$status" >>"$RESULTS"
  if [[ "$status" == passed ]]; then pass_count=$((pass_count + 1)); else fail_count=$((fail_count + 1)); fi
done <"$RUN_DIR/selection.tsv"

python3 - "$RESULTS" "$RUN_DIR/summary.json" "$case_count" "$pass_count" "$fail_count" <<'PY'
import json, sys
from pathlib import Path
results = [json.loads(line) for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()]
summary = {"case_dialect_executions": int(sys.argv[3]), "path_executions": int(sys.argv[3]) * 2, "passed": int(sys.argv[4]), "failed": int(sys.argv[5]), "results": results}
Path(sys.argv[2]).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
if summary["failed"]:
    raise SystemExit(f"SQLT-3E2 failed: {summary['passed']} passed, {summary['failed']} failed")
print(f"SQLT-3E2 passed: {summary['passed']} case/dialect and {summary['path_executions']} path executions")
PY
