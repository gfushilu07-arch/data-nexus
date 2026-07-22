/** Shared Prometheus text parsers for Admin UI (A06 / A08 / A10). */

export type SqlCursorMetricModes = {
  declare: number
  fetch: number
  close: number
  session_end: number
  unsupported: number
}

/**
 * A06 logical encode peaks from Prometheus (best-effort).
 * These are **not** process RSS / cgroup bytes — only encode-window high-water.
 */
export type EncodePeakMetrics = {
  /** Max of gateway_encode_peak_window_rows across series */
  peak_window_rows: number
  /** Max of gateway_encode_peak_window_bytes across series */
  peak_window_bytes: number
  /** Sum of gateway_encode_windows_total */
  encode_windows: number
  /** Sum of gateway_encode_bytes_total */
  encode_bytes: number
}

/**
 * execute_path counter buckets (A05/A08). Summed across label series.
 * Values are cumulative process counters, not rates.
 */
export type ExecutePathMetrics = {
  passthrough: number
  passthrough_client: number
  passthrough_extended: number
  passthrough_rewrite: number
  streaming: number
  streaming_demote: number
  materialized: number
  xproto_stream: number
  n_a: number
  other: number
  total: number
}

function promLineValue(ln: string): number {
  const m = ln.match(/\s([0-9]+(?:\.[0-9]+)?)\s*$/)
  return m ? Number(m[1]) || 0 : 0
}

/** Parse Prometheus text for A10 process-local SQL cursor modes (best-effort). */
export function parseSqlCursorMetrics(text: string): SqlCursorMetricModes {
  const out: SqlCursorMetricModes = {
    declare: 0,
    fetch: 0,
    close: 0,
    session_end: 0,
    unsupported: 0,
  }
  for (const ln of text.split('\n')) {
    if (!ln.includes('gateway_portal_resume_total') || ln.startsWith('#'))
      continue
    const m = ln.match(/mode="([^"]+)".*?\s([0-9]+(?:\.[0-9]+)?)\s*$/)
    if (!m)
      continue
    const mode = m[1]
    const n = Number(m[2]) || 0
    if (mode === 'sql_cursor_declare')
      out.declare += n
    else if (mode === 'sql_cursor_fetch')
      out.fetch += n
    else if (mode === 'sql_cursor_close')
      out.close += n
    else if (mode === 'sql_cursor_session_end')
      out.session_end += n
    else if (mode === 'sql_cursor_unsupported')
      out.unsupported += n
  }
  return out
}

/** Parse A06 logical peak / encode totals from Prometheus text. */
export function parseEncodePeakMetrics(text: string): EncodePeakMetrics {
  const out: EncodePeakMetrics = {
    peak_window_rows: 0,
    peak_window_bytes: 0,
    encode_windows: 0,
    encode_bytes: 0,
  }
  for (const ln of text.split('\n')) {
    if (ln.startsWith('#'))
      continue
    if (ln.includes('gateway_encode_peak_window_rows')) {
      const v = promLineValue(ln)
      if (v > out.peak_window_rows)
        out.peak_window_rows = v
    }
    else if (ln.includes('gateway_encode_peak_window_bytes')) {
      const v = promLineValue(ln)
      if (v > out.peak_window_bytes)
        out.peak_window_bytes = v
    }
    else if (ln.includes('gateway_encode_windows_total')) {
      out.encode_windows += promLineValue(ln)
    }
    else if (ln.includes('gateway_encode_bytes_total')) {
      out.encode_bytes += promLineValue(ln)
    }
  }
  return out
}

/** Parse A05/A08 execute_path counters from Prometheus text. */
export function parseExecutePathMetrics(text: string): ExecutePathMetrics {
  const out: ExecutePathMetrics = {
    passthrough: 0,
    passthrough_client: 0,
    passthrough_extended: 0,
    passthrough_rewrite: 0,
    streaming: 0,
    streaming_demote: 0,
    materialized: 0,
    xproto_stream: 0,
    n_a: 0,
    other: 0,
    total: 0,
  }
  for (const ln of text.split('\n')) {
    if (!ln.includes('gateway_execute_path_total') || ln.startsWith('#'))
      continue
    const m = ln.match(/execute_path="([^"]+)"/)
    const path = m?.[1] || 'other'
    const n = promLineValue(ln)
    out.total += n
    switch (path) {
      case 'passthrough':
        out.passthrough += n
        break
      case 'passthrough_client':
        out.passthrough_client += n
        break
      case 'passthrough_extended':
        out.passthrough_extended += n
        break
      case 'passthrough_rewrite':
        out.passthrough_rewrite += n
        break
      case 'streaming':
        out.streaming += n
        break
      case 'streaming_demote':
        out.streaming_demote += n
        break
      case 'materialized':
        out.materialized += n
        break
      case 'xproto_stream':
        out.xproto_stream += n
        break
      case 'n/a':
        out.n_a += n
        break
      default:
        out.other += n
        break
    }
  }
  return out
}
