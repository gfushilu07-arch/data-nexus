#!/usr/bin/env bash
# Execute the SQLT-4A same-protocol matrix through the mature suite runners.
set -euo pipefail

RUST_TOOLCHAIN_BIN="${RUST_TOOLCHAIN_BIN:-/Volumes/fushilu/.rustup/toolchains/1.94.1-aarch64-apple-darwin/bin}"
export PATH="/Applications/Docker.app/Contents/Resources/bin:$RUST_TOOLCHAIN_BIN:/opt/homebrew/bin:/usr/local/bin:${HOME}/.cargo/bin:${PATH:-}"
export CARGO_TARGET_DIR="${DATA_NEXUS_CARGO_TARGET_DIR:-/Volumes/fushilu/.caches/data-nexus/cargo-target}"
export RUSTUP_TOOLCHAIN="${RUSTUP_TOOLCHAIN:-1.94.1}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
CACHE_ROOT="${DATA_NEXUS_SQL_MATRIX_CACHE:-/Volumes/fushilu/.caches/data-nexus/sql-matrix}"
RUN_ID="${SQLT_PROTOCOL_MATRIX_RUN_ID:-protocol-matrix-$(date -u +%Y%m%dT%H%M%SZ)}"
RUN_DIR="$CACHE_ROOT/$RUN_ID"
SUITE_FILTER="${SQLT_PROTOCOL_MATRIX_SUITE:-}"
CASE_FROM="${SQLT_PROTOCOL_MATRIX_CASE_FROM:-}"
CASE_TO="${SQLT_PROTOCOL_MATRIX_CASE_TO:-}"
FILTERED=0
SUMMARY_ARGS=()
FAILED_SUITES=()

if [[ -n "$SUITE_FILTER$CASE_FROM$CASE_TO" ]]; then
  FILTERED=1
fi
if [[ -n "$CASE_FROM$CASE_TO" && -z "$SUITE_FILTER" ]]; then
  echo "case filtering requires SQLT_PROTOCOL_MATRIX_SUITE" >&2
  exit 1
fi
if [[ -n "$CASE_FROM" || -n "$CASE_TO" ]]; then
  [[ -n "$CASE_FROM" && -n "$CASE_TO" ]] || { echo "both case range endpoints are required" >&2; exit 1; }
  [[ "$CASE_FROM" < "$CASE_TO" || "$CASE_FROM" == "$CASE_TO" ]] || { echo "case range is reversed" >&2; exit 1; }
fi
case "$SUITE_FILTER" in
  ""|prepared|extended|cursor|tcl|dml|ddl) ;;
  *) echo "unknown protocol matrix suite: $SUITE_FILTER" >&2; exit 1 ;;
esac

mkdir -p "$RUN_DIR/logs" "$RUN_DIR/audit"
cp "$ROOT/protocol-matrix.json" "$ROOT/manifest.json" "$RUN_DIR/"

command -v docker >/dev/null 2>&1 || { echo "missing docker" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "missing python3" >&2; exit 1; }
python3 "$ROOT/validate.py" >"$RUN_DIR/logs/validate.log" 2>&1

docker ps --no-trunc --format '{{.ID}}\t{{.Names}}' | sort >"$RUN_DIR/audit/containers.before.tsv"
docker network ls --no-trunc --format '{{.ID}}\t{{.Name}}' | sort >"$RUN_DIR/audit/networks.before.tsv"
docker volume ls --format '{{.Name}}' | sort >"$RUN_DIR/audit/volumes.before.tsv"
pgrep -f 'target/.*/proxy daemon|target/.*/proxy --.*daemon' 2>/dev/null | sort -n >"$RUN_DIR/audit/gateway.before.tsv" || :

run_suite() {
  local suite="$1" runner="$2" child_id="$3" summary="$CACHE_ROOT/$child_id/summary.json"
  local upper="${suite^^}" env_args=()
  echo "==> SQLT-4A suite: $suite"
  env_args+=("SQLT_${upper}_RUN_ID=$child_id")
  if ((FILTERED)) && [[ -n "$CASE_FROM" ]]; then
    env_args+=("SQLT_${upper}_CASE_FROM=$CASE_FROM" "SQLT_${upper}_CASE_TO=$CASE_TO")
  fi
  if env -u SQLT_PREPARED_CASE_FROM -u SQLT_PREPARED_CASE_TO \
    -u SQLT_EXTENDED_CASE_FROM -u SQLT_EXTENDED_CASE_TO \
    -u SQLT_CURSOR_CASE_FROM -u SQLT_CURSOR_CASE_TO \
    -u SQLT_TCL_CASE_FROM -u SQLT_TCL_CASE_TO \
    -u SQLT_DML_CASE_FROM -u SQLT_DML_CASE_TO \
    -u SQLT_DDL_CASE_FROM -u SQLT_DDL_CASE_TO \
    "${env_args[@]}" "$ROOT/$runner" \
    >"$RUN_DIR/logs/${suite}.log" 2>&1; then
    :
  else
    FAILED_SUITES+=("$suite")
  fi
  [[ -s "$summary" ]] || FAILED_SUITES+=("$suite(summary-missing)")
  SUMMARY_ARGS+=(--summary "${suite}=${summary}")
}

[[ -n "$SUITE_FILTER" && "$SUITE_FILTER" != prepared ]] || run_suite prepared run-prepared-corpus.sh "$RUN_ID-prepared"
[[ -n "$SUITE_FILTER" && "$SUITE_FILTER" != extended ]] || run_suite extended run-extended-corpus.sh "$RUN_ID-extended"
[[ -n "$SUITE_FILTER" && "$SUITE_FILTER" != cursor ]] || run_suite cursor run-cursor-corpus.sh "$RUN_ID-cursor"
[[ -n "$SUITE_FILTER" && "$SUITE_FILTER" != tcl ]] || run_suite tcl run-tcl-corpus.sh "$RUN_ID-tcl"
[[ -n "$SUITE_FILTER" && "$SUITE_FILTER" != dml ]] || run_suite dml run-dml-corpus.sh "$RUN_ID-dml"
[[ -n "$SUITE_FILTER" && "$SUITE_FILTER" != ddl ]] || run_suite ddl run-ddl-corpus.sh "$RUN_ID-ddl"

docker ps --no-trunc --format '{{.ID}}\t{{.Names}}' | sort >"$RUN_DIR/audit/containers.after.tsv"
docker network ls --no-trunc --format '{{.ID}}\t{{.Name}}' | sort >"$RUN_DIR/audit/networks.after.tsv"
docker volume ls --format '{{.Name}}' | sort >"$RUN_DIR/audit/volumes.after.tsv"
pgrep -f 'target/.*/proxy daemon|target/.*/proxy --.*daemon' 2>/dev/null | sort -n >"$RUN_DIR/audit/gateway.after.tsv" || :

for resource in containers networks volumes gateway; do
  if ! comm -13 "$RUN_DIR/audit/${resource}.before.tsv" "$RUN_DIR/audit/${resource}.after.tsv" >"$RUN_DIR/audit/${resource}.residual.tsv"; then
    FAILED_SUITES+=("${resource}(snapshot)")
  fi
  [[ ! -s "$RUN_DIR/audit/${resource}.residual.tsv" ]] || FAILED_SUITES+=("${resource}(residual)")
done

if ((${#FAILED_SUITES[@]})); then
  printf 'SQLT-4A child failures or resource residue: %s\n' "${FAILED_SUITES[*]}" >&2
  exit 1
fi

AGGREGATE_FILTER=()
((FILTERED)) && AGGREGATE_FILTER+=(--filtered)
python3 "$ROOT/protocol_matrix.py" "$ROOT/protocol-matrix.json" "$ROOT/manifest.json" "$ROOT" \
  "$RUN_DIR/summary.json" --run-id "$RUN_ID" "${AGGREGATE_FILTER[@]}" "${SUMMARY_ARGS[@]}" \
  >"$RUN_DIR/logs/aggregate.log" 2>&1
python3 - "$RUN_DIR/summary.json" <<'PY'
import json, sys
from pathlib import Path
summary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
summary["child_run_ids"] = {
    suite: f"{summary['run_id']}-{suite}" if "run_id" in summary else None
    for suite in summary.get("suites", {})
}
Path(sys.argv[1]).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
if ((FILTERED)); then
  printf 'SQLT-4A reproduction passed with acceptance_complete=false\nartifacts: %s\n' "$RUN_DIR"
else
  printf 'SQLT-4A passed: 6 suites, 4 lanes, 376 paths\nartifacts: %s\n' "$RUN_DIR"
fi
