#!/usr/bin/env bash
# Execute SQLT-4B1 across MySQL text -> PostgreSQL and PostgreSQL simple -> MySQL.
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
RUN_ID="${SQLT_CROSS_PROTOCOL_RUN_ID:-cross-protocol-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
DIRECTION="${SQLT_CROSS_PROTOCOL_DIRECTION:-}"
CASE_FROM="${SQLT_CROSS_PROTOCOL_CASE_FROM:-}"
CASE_TO="${SQLT_CROSS_PROTOCOL_CASE_TO:-}"
FILTERED=0
RUN_TOKEN="$(printf '%s' "$RUN_ID" | tr -cd '[:alnum:]')"
[[ -n "$RUN_TOKEN" ]] || { echo "run ID needs an ASCII alphanumeric character" >&2; exit 1; }
COMPOSE_PROJECT="sqlt4b1-$RUN_TOKEN"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
GATEWAY_CONFIG="$ROOT/fixtures/cross-protocol-gateway-config.toml"
GATEWAY_PID=""
RESULTS="$RUN_DIR/results.jsonl"
SELECTION="$RUN_DIR/selection.jsonl"
CLIENT_IMAGE="${SQLT_CROSS_PROTOCOL_CLIENT_IMAGE:-sqlt-cross-protocol-client:9.4.0}"
RUN_LABEL=(--label "data-nexus.sql-matrix.run-id=$RUN_ID")

if [[ -n "$DIRECTION$CASE_FROM$CASE_TO" ]]; then FILTERED=1; fi
case "$DIRECTION" in
  ""|mysql_text_to_postgres|pg_simple_to_mysql) ;;
  *) echo "unknown cross-protocol direction: $DIRECTION" >&2; exit 1 ;;
esac
if [[ -n "$CASE_FROM" || -n "$CASE_TO" ]]; then
  [[ -n "$CASE_FROM" && -n "$CASE_TO" ]] || { echo "both case range endpoints are required" >&2; exit 1; }
  [[ "$CASE_FROM" < "$CASE_TO" || "$CASE_FROM" == "$CASE_TO" ]] || { echo "case range is reversed" >&2; exit 1; }
fi

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/selections" "$RUN_DIR/audit"
: >"$RESULTS"
cp "$ROOT/cross-protocol-matrix.json" "$ROOT/cross-protocol-oracles.json" \
  "$ROOT/dql-oracles.json" "$ROOT/manifest.json" "$ROOT/capabilities.json" \
  "$GATEWAY_CONFIG" "$RUN_DIR/"

snapshot_resources() {
  local suffix="$1"
  docker ps -a --no-trunc \
    --format '{{.ID}}\t{{.Names}}\t{{.Label "com.docker.compose.project"}}\t{{.Label "data-nexus.sql-matrix.run-id"}}' \
    | sort >"$RUN_DIR/audit/containers.$suffix.tsv"
  docker network ls --no-trunc \
    --format '{{.ID}}\t{{.Name}}\t{{.Label "com.docker.compose.project"}}' \
    | sort >"$RUN_DIR/audit/networks.$suffix.tsv"
  docker volume ls --format '{{.Name}}\t{{.Label "com.docker.compose.project"}}' \
    | sort >"$RUN_DIR/audit/volumes.$suffix.tsv"
}

cleanup_owned() {
  local client_ids
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  client_ids="$(docker ps -aq --filter "label=data-nexus.sql-matrix.run-id=$RUN_ID" || true)"
  if [[ -n "$client_ids" ]]; then
    docker rm -f $client_ids >/dev/null 2>&1 || true
  fi
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}

finish() {
  local status=$?
  local gateway_command=""
  trap - EXIT INT TERM
  if [[ -n "$GATEWAY_PID" ]]; then
    gateway_command="$(ps -p "$GATEWAY_PID" -o command= 2>/dev/null || true)"
    printf '%s\t%s\n' "$GATEWAY_PID" "$gateway_command" >"$RUN_DIR/audit/gateway.pid.tsv"
  fi
  cleanup_owned
  snapshot_resources after || status=1
  {
    docker ps -aq --filter "label=com.docker.compose.project=$COMPOSE_PROJECT"
    docker ps -aq --filter "label=data-nexus.sql-matrix.run-id=$RUN_ID"
  } | sed '/^$/d' | sort -u >"$RUN_DIR/audit/containers.residual.tsv"
  docker network ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
    | sort -u >"$RUN_DIR/audit/networks.residual.tsv"
  docker volume ls -q --filter "label=com.docker.compose.project=$COMPOSE_PROJECT" \
    | sort -u >"$RUN_DIR/audit/volumes.residual.tsv"
  : >"$RUN_DIR/audit/gateway.residual.tsv"
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    ps -p "$GATEWAY_PID" -o pid=,command= >"$RUN_DIR/audit/gateway.residual.tsv" || true
  fi
  for resource in containers networks volumes gateway; do
    if [[ -s "$RUN_DIR/audit/${resource}.residual.tsv" ]]; then
      echo "SQLT-4B1 left owned $resource resources" >&2
      status=1
    fi
  done
  exit "$status"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

command -v docker >/dev/null 2>&1 || { echo "missing docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing python3" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || { echo "missing curl" >&2; exit 1; }
command -v rustup >/dev/null 2>&1 || { echo "missing rustup" >&2; exit 1; }
[[ "$(rustup run "$RUSTUP_TOOLCHAIN" rustc --version)" == rustc\ 1.94.1\ * ]] || {
  echo "SQLT-4B1 requires rustc 1.94.1" >&2
  exit 1
}

snapshot_resources before

python3 "$ROOT/validate.py" >"$RUN_DIR/logs/validate.log" 2>&1

selector_args=(
  "$ROOT/cross-protocol-matrix.json"
  "$ROOT/manifest.json"
  "$ROOT/cross-protocol-oracles.json"
  "$ROOT/dql-oracles.json"
  "$ROOT"
)
[[ -z "$DIRECTION" ]] || selector_args+=(--direction "$DIRECTION")
if [[ -n "$CASE_FROM" ]]; then selector_args+=(--case-from "$CASE_FROM" --case-to "$CASE_TO"); fi
python3 "$ROOT/select_cross_protocol_cases.py" "${selector_args[@]}" >"$SELECTION"
[[ -s "$SELECTION" ]] || { echo "cross-protocol selection is empty" >&2; exit 1; }

docker build --pull=false -t "$CLIENT_IMAGE" -f - . >"$RUN_DIR/logs/client-image-build.log" 2>&1 <<'DOCKERFILE'
FROM python:3.12-slim-bookworm
RUN pip install --no-cache-dir --disable-pip-version-check "mysql-connector-python==9.4.0"
DOCKERFILE

echo "==> starting fixed MySQL 8.0.42 and PostgreSQL 16.8 fixtures"
"${COMPOSE[@]}" up -d >"$RUN_DIR/logs/compose-up.log" 2>&1
for _ in $(seq 1 90); do
  mysql_ok="$("${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent 2>/dev/null || true)"
  pg_ok="$("${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt 2>/dev/null || true)"
  if [[ "$mysql_ok" == *"mysqld is alive"* && "$pg_ok" == *"accepting connections"* ]]; then break; fi
  sleep 2
done
"${COMPOSE[@]}" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -proot --silent
"${COMPOSE[@]}" exec -T postgres pg_isready -U sqlt -d sqlt

run_mysql_fixture() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$1"
}
run_postgres_fixture() {
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 \
    -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt <"$1"
}
for phase in cleanup schema seed; do
  run_mysql_fixture "$ROOT/fixtures/mysql/$phase.sql" >"$RUN_DIR/logs/mysql-$phase.out"
  run_postgres_fixture "$ROOT/fixtures/postgres/$phase.sql" >"$RUN_DIR/logs/postgres-$phase.out"
done

GATEWAY_BIN="$CARGO_TARGET_DIR/debug/proxy"
if [[ "${SQLT_FORCE_BUILD:-0}" == "1" || ! -x "$GATEWAY_BIN" ]]; then
  (cd "$PROJECT_ROOT" && rustup run "$RUSTUP_TOOLCHAIN" cargo build -p data-proxy --bin proxy) \
    >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" >"$RUN_DIR/logs/cargo-build.log"
fi
[[ -x "$GATEWAY_BIN" ]] || { echo "gateway binary not found: $GATEWAY_BIN" >&2; exit 1; }
"$GATEWAY_BIN" daemon -c "$GATEWAY_CONFIG" >"$RUN_DIR/logs/gateway.log" 2>&1 &
GATEWAY_PID=$!
printf '%s\n' "$GATEWAY_PID" >"$RUN_DIR/gateway.pid"
for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:28083/admin/listeners >"$RUN_DIR/logs/listeners.json" 2>/dev/null; then break; fi
  if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
    echo "gateway exited early; see $RUN_DIR/logs/gateway.log" >&2
    exit 1
  fi
  sleep 1
done
curl -fsS http://127.0.0.1:28083/admin/listeners >"$RUN_DIR/logs/listeners.json"
python3 - "$RUN_DIR/logs/listeners.json" <<'PY'
import json, sys
names = sorted(item["name"] for item in json.load(open(sys.argv[1], encoding="utf-8")))
expected = ["sqlt-mysql-to-postgres", "sqlt-postgres-to-mysql"]
if names != expected:
    raise SystemExit(f"listener mismatch: {names!r}")
PY

run_client() {
  local protocol="$1" port="$2" user="$3" password="$4" sql_file="$5" output="$6"
  docker run --rm "${RUN_LABEL[@]}" --add-host=host.docker.internal:host-gateway \
    -v "$ROOT:/matrix:ro" "$CLIENT_IMAGE" \
    python /matrix/cross_protocol_client.py --protocol "$protocol" \
    --sql "/matrix/cases/$sql_file" --host host.docker.internal --port "$port" \
    --user "$user" --password "$password" --database sqlt \
    >"$output" 2>"${output%.json}.err"
}

append_failed() {
  local selection_file="$1" backend_file="$2" gateway_file="$3" reproduction="$4" error="$5"
  python3 - "$selection_file" "$backend_file" "$gateway_file" "$reproduction" "$error" >>"$RESULTS" <<'PY'
import json, sys
selection = json.load(open(sys.argv[1], encoding="utf-8"))
print(json.dumps({
    "case_id": selection["case_id"], "source_case_id": selection["source_case_id"],
    "direction": selection["direction"], "frontend": selection["frontend"],
    "backend": selection["backend"], "protocol": selection["protocol"],
    "status": "failed", "backend_control_evidence": sys.argv[2],
    "gateway_evidence": sys.argv[3], "type_map": None,
    "rewrite_tags": selection["rewrite_tags"], "row_count": None,
    "reproduction": sys.argv[4], "error": sys.argv[5],
}, sort_keys=True))
PY
}

path_count=0
while IFS= read -r selection_record; do
  [[ -n "$selection_record" ]] || continue
  fields="$(python3 -c 'import json,sys; v=json.loads(sys.argv[1]); print("\t".join(str(v[k]) for k in ("case_id","direction","protocol","port","backend_control_protocol","backend_control_port","sql_file","backend_sql_file")))' "$selection_record")"
  IFS=$'\t' read -r case_id direction protocol port backend_protocol backend_port sql_file backend_sql_file <<<"$fields"
  path_count=$((path_count + 1))
  stem="${case_id}-${direction}"
  selection_file="$RUN_DIR/selections/$stem.json"
  backend_file="$RUN_DIR/results/$stem.backend.json"
  gateway_file="$RUN_DIR/results/$stem.gateway.json"
  printf '%s\n' "$selection_record" >"$selection_file"
  reproduction="SQLT_CROSS_PROTOCOL_DIRECTION=$direction SQLT_CROSS_PROTOCOL_CASE_FROM=$case_id SQLT_CROSS_PROTOCOL_CASE_TO=$case_id SQLT_CROSS_PROTOCOL_RUN_ID=${RUN_ID}-repro $ROOT/run-cross-protocol-matrix.sh"
  echo "==> $case_id [$direction backend-control + gateway]"

  backend_user=root
  backend_password=root
  if [[ "$backend_protocol" == pg_simple ]]; then backend_user=sqlt; backend_password=sqlt; fi
  status=passed
  if ! run_client "$backend_protocol" "$backend_port" "$backend_user" "$backend_password" \
    "$backend_sql_file" "$backend_file"; then status=backend-client-failed; fi
  if ! run_client "$protocol" "$port" root root "$sql_file" "$gateway_file"; then
    status=gateway-client-failed
  fi
  if [[ "$status" == passed ]]; then
    if ! python3 "$ROOT/cross_protocol_matrix.py" compare \
      --selection "$selection_file" --backend "$backend_file" --gateway "$gateway_file" \
      --backend-evidence "$backend_file" --gateway-evidence "$gateway_file" \
      --reproduction "$reproduction" >>"$RESULTS" 2>"$RUN_DIR/logs/$stem.compare.err"; then
      status=oracle-mismatch
    fi
  fi
  if [[ "$status" != passed ]]; then
    append_failed "$selection_file" "$backend_file" "$gateway_file" "$reproduction" "$status"
  fi
done <"$SELECTION"

aggregate_args=(
  aggregate --selection "$SELECTION" --results "$RESULTS"
  --output "$RUN_DIR/summary.json" --run-id "$RUN_ID" --run-dir "$RUN_DIR"
)
if ((FILTERED)); then aggregate_args+=(--filtered); fi
python3 "$ROOT/cross_protocol_matrix.py" "${aggregate_args[@]}" \
  >"$RUN_DIR/logs/aggregate.log" 2>&1

if ((FILTERED)); then
  printf 'SQLT-4B1 reproduction passed with acceptance_complete=false\nartifacts: %s\n' "$RUN_DIR"
else
  printf 'SQLT-4B1 passed: 2 lanes, 12 cases, 24 paths\nartifacts: %s\n' "$RUN_DIR"
fi
