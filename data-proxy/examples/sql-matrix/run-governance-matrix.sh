#!/usr/bin/env bash
# Execute SQLT-5A: governance policy matrix across security_off / deny_dml /
# deny_select_targets / row_filter_tenant10 on MySQL text and PostgreSQL simple.
set -euo pipefail

RUST_TOOLCHAIN_BIN="${RUST_TOOLCHAIN_BIN:-/Volumes/fushilu/.rustup/toolchains/1.94.1-aarch64-apple-darwin/bin}"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$RUST_TOOLCHAIN_BIN:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"
export CARGO_TARGET_DIR="${DATA_NEXUS_CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_HOME="${RUSTUP_HOME:-/Volumes/fushilu/.rustup}"
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.94.1}"

ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$ROOT/../.." && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_GOVERNANCE_RUN_ID:-governance-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
PROTOCOL_FILTER="${SQLT_GOVERNANCE_PROTOCOL:-}"
POLICY_FILTER="${SQLT_GOVERNANCE_POLICY:-}"
CASE_FROM="${SQLT_GOVERNANCE_CASE_FROM:-}"
CASE_TO="${SQLT_GOVERNANCE_CASE_TO:-}"
FILTERED=0
RUN_TOKEN="$(printf '%s' "$RUN_ID" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]')"
[[ -n "$RUN_TOKEN" ]] || { echo "run ID needs an ASCII alphanumeric character" >&2; exit 1; }
COMPOSE_PROJECT="sqlt5-$RUN_TOKEN"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT" -f "$ROOT/fixtures/docker-compose.yml")
GATEWAY_PID=""
RESULTS="$RUN_DIR/results.jsonl"
SELECTION="$RUN_DIR/selection.jsonl"
CLIENT_IMAGE="${SQLT_GOVERNANCE_CLIENT_IMAGE:-sqlt-cross-protocol-dml-client:9.4.0}"
RUN_LABEL=(--label "data-nexus.sql-matrix.run-id=$RUN_ID")

if [[ -n "$PROTOCOL_FILTER$POLICY_FILTER$CASE_FROM$CASE_TO" ]]; then FILTERED=1; fi
case "$PROTOCOL_FILTER" in
  ""|mysql_text_to_mysql|pg_simple_to_postgres) ;;
  *) echo "unknown governance protocol: $PROTOCOL_FILTER" >&2; exit 1 ;;
esac
case "$POLICY_FILTER" in
  ""|security_off|deny_dml|deny_select_targets|row_filter_tenant10|column_strip_amount|mask_pii|watermark_column|max_rows_1|audit_l0|audit_l1|audit_l2) ;;
  *) echo "unknown governance policy: $POLICY_FILTER" >&2; exit 1 ;;
esac
if [[ -n "$CASE_FROM" || -n "$CASE_TO" ]]; then
  [[ -n "$CASE_FROM" && -n "$CASE_TO" ]] || {
    echo "both case range endpoints are required" >&2; exit 1
  }
  [[ "$CASE_FROM" < "$CASE_TO" || "$CASE_FROM" == "$CASE_TO" ]] || {
    echo "case range is reversed" >&2; exit 1
  }
fi

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/results" "$RUN_DIR/selections" "$RUN_DIR/audit"
: >"$RESULTS"
cp "$ROOT/governance-matrix.json" "$ROOT/governance-oracles.json" "$RUN_DIR/"

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
  GATEWAY_PID=""
  client_ids="$(docker ps -aq --filter "label=data-nexus.sql-matrix.run-id=$RUN_ID" || true)"
  if [[ -n "$client_ids" ]]; then
    docker rm -f $client_ids >/dev/null 2>&1 || true
  fi
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
}

finish() {
  local status=$?
  trap - EXIT INT TERM
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
  if pgrep -f "proxy daemon -c .*governance-" >/dev/null 2>&1; then
    pgrep -f "proxy daemon -c .*governance-" >"$RUN_DIR/audit/gateway.residual.tsv" || true
  fi
  for resource in containers networks volumes gateway; do
    if [[ -s "$RUN_DIR/audit/${resource}.residual.tsv" ]]; then
      echo "SQLT-5 left owned $resource resources" >&2
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
  echo "SQLT-5 requires rustc 1.94.1" >&2
  exit 1
}

snapshot_resources before
python3 "$ROOT/validate.py" >"$RUN_DIR/logs/validate.log" 2>&1

selector_args=(
  "$ROOT/governance-matrix.json"
  "$ROOT/governance-oracles.json"
  "$ROOT"
)
[[ -z "$PROTOCOL_FILTER" ]] || selector_args+=(--protocol "$PROTOCOL_FILTER")
[[ -z "$POLICY_FILTER" ]] || selector_args+=(--policy "$POLICY_FILTER")
if [[ -n "$CASE_FROM" ]]; then
  selector_args+=(--case-from "$CASE_FROM" --case-to "$CASE_TO")
fi
python3 "$ROOT/select_governance_cases.py" "${selector_args[@]}" >"$SELECTION"
[[ -s "$SELECTION" ]] || { echo "governance selection is empty" >&2; exit 1; }

echo "==> starting fixed MySQL 8.0.42 and PostgreSQL 16.8 fixtures"
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

run_mysql_fixture() {
  "${COMPOSE[@]}" exec -T mysql mysql --batch --raw --skip-column-names \
    --default-character-set=utf8mb4 --protocol=TCP -h 127.0.0.1 -uroot -proot sqlt <"$1"
}

run_postgres_fixture() {
  "${COMPOSE[@]}" exec -T postgres psql -X -q -v ON_ERROR_STOP=1 \
    -P null=NULL -A -t -F $'\t' -U sqlt -d sqlt <"$1"
}

reset_backend() {
  local backend="$1" prefix="$2" phase
  for phase in cleanup schema seed; do
    if [[ "$backend" == "mysql" ]]; then
      run_mysql_fixture "$ROOT/fixtures/mysql/$phase.sql" \
        >"$prefix-mysql-$phase.out" 2>"$prefix-mysql-$phase.err" || return 1
    else
      run_postgres_fixture "$ROOT/fixtures/postgres/$phase.sql" \
        >"$prefix-postgres-$phase.out" 2>"$prefix-postgres-$phase.err" || return 1
    fi
  done
}

GATEWAY_BIN="$CARGO_TARGET_DIR/debug/proxy"
if [[ "${SQLT_FORCE_BUILD:-0}" == "1" || ! -x "$GATEWAY_BIN" ]]; then
  (cd "$PROJECT_ROOT" && rustup run "$RUSTUP_TOOLCHAIN" cargo build -p data-proxy --bin proxy) \
    >"$RUN_DIR/logs/cargo-build.log" 2>&1
else
  echo "reusing cached gateway binary: $GATEWAY_BIN" >"$RUN_DIR/logs/cargo-build.log"
fi
[[ -x "$GATEWAY_BIN" ]] || { echo "gateway binary not found: $GATEWAY_BIN" >&2; exit 1; }

start_gateway() {
  local policy="$1"
  "$GATEWAY_BIN" daemon -c "$ROOT/$(policy_config "$policy")" \
    >"$RUN_DIR/logs/gateway-$policy.log" 2>&1 &
  GATEWAY_PID=$!
  for _ in $(seq 1 90); do
    if curl -fsS http://127.0.0.1:28084/admin/listeners \
      >"$RUN_DIR/logs/listeners-$policy.json" 2>/dev/null; then
      break
    fi
    if ! kill -0 "$GATEWAY_PID" 2>/dev/null; then
      echo "gateway exited early for $policy; see $RUN_DIR/logs/gateway-$policy.log" >&2
      exit 1
    fi
    sleep 1
  done
  curl -fsS http://127.0.0.1:28084/admin/listeners >"$RUN_DIR/logs/listeners-$policy.json"
  AUDIT_BASELINE_LINES=0
  policy_audit_file="$(python3 -c 'import json,sys; v=json.load(open(sys.argv[1], encoding="utf-8")); print((v["policies"].get(sys.argv[2]) or {}).get("audit_file") or "")' "$ROOT/governance-matrix.json" "$policy")"
  if [[ -n "$policy_audit_file" && -f "$policy_audit_file" ]]; then
    AUDIT_BASELINE_LINES="$(wc -l <"$policy_audit_file" | tr -d ' ')"
  fi
  python3 - "$RUN_DIR/logs/listeners-$policy.json" <<'PY'
import json, sys
names = sorted(item["name"] for item in json.load(open(sys.argv[1], encoding="utf-8")))
expected = ["sqlt-governance-mysql", "sqlt-governance-postgresql"]
if names != expected:
    raise SystemExit(f"listener mismatch: {names!r}")
PY
}

stop_gateway() {
  if [[ -n "$GATEWAY_PID" ]] && kill -0 "$GATEWAY_PID" 2>/dev/null; then
    kill "$GATEWAY_PID" 2>/dev/null || true
    wait "$GATEWAY_PID" 2>/dev/null || true
  fi
  GATEWAY_PID=""
}

run_steps() {
  local protocol="$1" port="$2" sql_file="$3" output="$4"
  docker run --rm "${RUN_LABEL[@]}" --add-host=host.docker.internal:host-gateway \
    -v "$ROOT:/matrix:ro" "$CLIENT_IMAGE" \
    python /matrix/cross_protocol_dml_client.py --protocol "$protocol" \
    --sql "/matrix/cases/$sql_file" --host host.docker.internal --port "$port" \
    --user root --password root --database sqlt \
    >"$output" 2>"${output%.json}.err"
}

# Governance case files are shared across policies: a denied step exits the
# client 1 by design (no @expect annotation can be policy-aware). Exit 1 is
# fine as long as a transcript was produced; anything else is a real failure.
run_steps_tolerant() {
  local protocol="$1" port="$2" sql_file="$3" output="$4"
  set +e
  run_steps "$protocol" "$port" "$sql_file" "$output"
  local rc=$?
  set -e
  [[ $rc -le 1 && -s "$output" ]]
}

run_state() {
  # Native backend connection: policy rewrites (row filters) must never
  # distort the backend canary, so state evidence bypasses the gateway.
  local protocol="$1" sql_file="$2" output="$3"
  local port=23306 user=root password=root
  if [[ "$protocol" == "pg_simple" ]]; then
    port=25432 user=sqlt password=sqlt
  fi
  docker run --rm "${RUN_LABEL[@]}" --add-host=host.docker.internal:host-gateway \
    -v "$ROOT:/matrix:ro" "$CLIENT_IMAGE" \
    python /matrix/cross_protocol_client.py --protocol "$protocol" \
    --sql "/matrix/$sql_file" --host host.docker.internal --port "$port" \
    --user "$user" --password "$password" --database sqlt \
    >"$output" 2>"${output%.json}.err"
}

append_failed() {
  local selection_file="$1" reproduction="$2" error="$3"
  shift 3
  python3 - "$selection_file" "$reproduction" "$error" "$@" >>"$RESULTS" <<'PY'
import json, sys
selection = json.load(open(sys.argv[1], encoding="utf-8"))
paths = sys.argv[4:]
print(json.dumps({
    "case_id": selection["case_id"], "name": selection["name"],
    "policy": selection["policy"], "protocol": selection["protocol"],
    "frontend": selection["frontend"], "backend": selection["backend"],
    "status": "failed", "evidence_paths": paths,
    "reproduction": sys.argv[2], "error": sys.argv[3],
}, sort_keys=True))
PY
}

policy_config() {
  case "$1" in
    security_off) echo "fixtures/governance-security-off-gateway-config.toml" ;;
    deny_dml) echo "fixtures/governance-deny-dml-gateway-config.toml" ;;
    deny_select_targets) echo "fixtures/governance-deny-select-targets-gateway-config.toml" ;;
    row_filter_tenant10) echo "fixtures/governance-row-filter-tenant10-gateway-config.toml" ;;
    column_strip_amount) echo "fixtures/governance-column-strip-amount-gateway-config.toml" ;;
    mask_pii) echo "fixtures/governance-mask-pii-gateway-config.toml" ;;
    watermark_column) echo "fixtures/governance-watermark-column-gateway-config.toml" ;;
    max_rows_1) echo "fixtures/governance-max-rows-1-gateway-config.toml" ;;
    audit_l0) echo "fixtures/governance-audit-l0-gateway-config.toml" ;;
    audit_l1) echo "fixtures/governance-audit-l1-gateway-config.toml" ;;
    audit_l2) echo "fixtures/governance-audit-l2-gateway-config.toml" ;;
    *) echo "unknown governance policy: $1" >&2; return 1 ;;
  esac
}

CURRENT_POLICY=""
while IFS= read -r selection_record; do
  [[ -n "$selection_record" ]] || continue
  fields="$(python3 -c 'import json,sys; v=json.loads(sys.argv[1]); print("\t".join(str(v[k]) for k in ("case_id","policy","protocol","client_protocol","port","backend","sql_file","backend_sql_file","state_query")))' "$selection_record")"
  IFS=$'\t' read -r case_id policy protocol client_protocol port backend \
    sql_file backend_sql_file state_query <<<"$fields"
  stem="$case_id-$policy-$protocol"
  selection_file="$RUN_DIR/selections/$stem.json"
  gateway_before="$RUN_DIR/results/$stem.gateway-before.json"
  gateway_transcript="$RUN_DIR/results/$stem.gateway-transcript.json"
  gateway_after="$RUN_DIR/results/$stem.gateway-after.json"
  evidence=("$gateway_before" "$gateway_transcript" "$gateway_after")
  printf '%s\n' "$selection_record" >"$selection_file"
  reproduction="SQLT_GOVERNANCE_POLICY=$policy SQLT_GOVERNANCE_PROTOCOL=$protocol SQLT_GOVERNANCE_CASE_FROM=$case_id SQLT_GOVERNANCE_CASE_TO=$case_id SQLT_GOVERNANCE_RUN_ID=${RUN_ID}-repro $ROOT/run-governance-matrix.sh"

  if [[ "$policy" != "$CURRENT_POLICY" ]]; then
    stop_gateway
    start_gateway "$policy"
    CURRENT_POLICY="$policy"
  fi
  echo "==> $case_id [$policy / $protocol]"

  status=passed
  if ! reset_backend "$backend" "$RUN_DIR/logs/$stem.reset"; then
    status=backend-reset-failed
  elif ! run_state "$client_protocol" "$state_query" "$gateway_before"; then
    status=gateway-before-state-failed
  elif ! run_steps_tolerant "$client_protocol" "$port" "$sql_file" "$gateway_transcript"; then
    status=gateway-client-failed
  elif ! run_state "$client_protocol" "$state_query" "$gateway_after"; then
    status=gateway-after-state-failed
  fi

  audit_evidence="$RUN_DIR/results/$stem.audit.jsonl"
  : >"$audit_evidence"
  if [[ -n "${policy_audit_file:-}" && -f "$policy_audit_file" ]]; then
    tail -n +"$((AUDIT_BASELINE_LINES + 1))" "$policy_audit_file" >"$audit_evidence" 2>/dev/null || true
  fi
  evidence+=("$audit_evidence")

  if [[ "$status" == passed ]]; then
    if ! python3 "$ROOT/governance_matrix.py" compare \
      --selection "$selection_file" \
      --gateway-before "$gateway_before" \
      --gateway-transcript "$gateway_transcript" \
      --gateway-after "$gateway_after" \
      --audit-evidence "$audit_evidence" \
      --reproduction "$reproduction" \
      >>"$RESULTS" 2>"$RUN_DIR/logs/$stem.compare.err"; then
      status=oracle-mismatch
    fi
  fi
  if [[ "$status" != passed ]]; then
    append_failed "$selection_file" "$reproduction" "$status" "${evidence[@]}"
  fi
done <"$SELECTION"
stop_gateway

aggregate_args=(
  aggregate --selection "$SELECTION" --results "$RESULTS"
  --output "$RUN_DIR/summary.json" --run-id "$RUN_ID" --run-dir "$RUN_DIR"
)
if ((FILTERED)); then aggregate_args+=(--filtered); fi
python3 "$ROOT/governance_matrix.py" "${aggregate_args[@]}" \
  >"$RUN_DIR/logs/aggregate.log" 2>&1

if ((FILTERED)); then
  printf 'SQLT-5 reproduction passed with acceptance_complete=false\nartifacts: %s\n' "$RUN_DIR"
else
  printf 'SQLT-5 passed: 11 policies x 5 cases x 2 protocols = 110 paths\nartifacts: %s\n' "$RUN_DIR"
fi
