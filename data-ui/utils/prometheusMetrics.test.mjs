/**
 * UI38/UI39/UI41: pure-function checks for Prometheus metric parsers.
 * Run: node --experimental-strip-types --test utils/prometheusMetrics.test.mjs
 */
import { strict as assert } from 'node:assert'
import { describe, it } from 'node:test'
import {
  parseEncodePeakMetrics,
  parseExecutePathMetrics,
  parsePortalHttpMetrics,
  parsePortalResumeMetrics,
  parseSecurePathMetrics,
  parseSqlCursorMetrics,
} from './prometheusMetrics.ts'

const SAMPLE = `
# HELP gateway_encode_peak_window_rows logical peak
# TYPE gateway_encode_peak_window_rows gauge
unisql_proxy_gateway_encode_peak_window_rows{listener="pg",command_type="Query"} 2
unisql_proxy_gateway_encode_peak_window_rows{listener="mysql",command_type="Query"} 1
unisql_proxy_gateway_encode_peak_window_bytes{listener="pg"} 128
unisql_proxy_gateway_encode_peak_window_bytes{listener="mysql"} 64
unisql_proxy_gateway_encode_windows_total{listener="pg"} 5
unisql_proxy_gateway_encode_windows_total{listener="mysql"} 3
unisql_proxy_gateway_encode_bytes_total{listener="pg"} 1000
unisql_proxy_gateway_encode_bytes_total{listener="mysql"} 400
unisql_proxy_gateway_execute_path_total{execute_path="streaming",listener="pg"} 10
unisql_proxy_gateway_execute_path_total{execute_path="streaming_demote",listener="mysql"} 2
unisql_proxy_gateway_execute_path_total{execute_path="passthrough",listener="pg"} 7
unisql_proxy_gateway_execute_path_total{execute_path="passthrough_client",listener="pg"} 3
unisql_proxy_gateway_execute_path_total{execute_path="passthrough_extended",listener="pg"} 1
unisql_proxy_gateway_execute_path_total{execute_path="passthrough_rewrite",listener="pg"} 1
unisql_proxy_gateway_execute_path_total{execute_path="xproto_stream",listener="portal"} 4
unisql_proxy_gateway_execute_path_total{execute_path="materialized",listener="pg"} 1
unisql_proxy_gateway_execute_path_total{execute_path="n/a",listener="pg"} 2
unisql_proxy_gateway_portal_resume_total{mode="sql_cursor_declare"} 2
unisql_proxy_gateway_portal_resume_total{mode="sql_cursor_fetch"} 5
unisql_proxy_gateway_portal_resume_total{mode="sql_cursor_close"} 1
unisql_proxy_gateway_portal_resume_total{mode="sql_cursor_session_end"} 1
unisql_proxy_gateway_portal_resume_total{mode="sql_cursor_unsupported"} 3
unisql_proxy_gateway_portal_resume_total{mode="hold"} 9
unisql_proxy_gateway_portal_resume_total{mode="resume_hold"} 4
unisql_proxy_gateway_portal_resume_total{mode="logical_skip"} 2
unisql_proxy_gateway_execute_path_total{type="PORTAL_STREAM",execute_path="streaming",listener="admin"} 6
unisql_proxy_gateway_execute_path_total{type="PORTAL_STREAM",execute_path="xproto_stream",listener="admin"} 2
unisql_proxy_gateway_execute_path_total{type="PORTAL_CHUNKED",execute_path="materialized",listener="admin"} 3
unisql_proxy_gateway_encode_peak_window_rows{type="PORTAL_STREAM",listener="admin"} 2
unisql_proxy_gateway_encode_peak_window_rows{type="PORTAL_CHUNKED",listener="admin"} 50
unisql_proxy_gateway_mask_rows_total{listener="pg"} 12
unisql_proxy_gateway_mask_rows_total{listener="mysql"} 3
unisql_proxy_gateway_passthrough_bytes_total{listener="pg"} 2048
unisql_proxy_gateway_passthrough_bytes_total{listener="mysql"} 512
`

describe('parseEncodePeakMetrics', () => {
  it('takes max peak rows/bytes across all series and sums windows/bytes', () => {
    const p = parseEncodePeakMetrics(SAMPLE)
    // Includes PORTAL_CHUNKED peak=50 (process-wide high-water; not filtered by type)
    assert.equal(p.peak_window_rows, 50)
    assert.equal(p.peak_window_bytes, 128)
    assert.equal(p.encode_windows, 8)
    assert.equal(p.encode_bytes, 1400)
  })

  it('ignores HELP/TYPE and empty text', () => {
    const empty = parseEncodePeakMetrics('# HELP x\n')
    assert.equal(empty.peak_window_rows, 0)
    assert.equal(empty.encode_windows, 0)
  })
})

describe('parseExecutePathMetrics', () => {
  it('buckets execute_path counters including portal type series', () => {
    const e = parseExecutePathMetrics(SAMPLE)
    // protocol streaming 10 + PORTAL_STREAM streaming 6
    assert.equal(e.streaming, 16)
    assert.equal(e.streaming_demote, 2)
    assert.equal(e.passthrough, 7)
    assert.equal(e.passthrough_client, 3)
    assert.equal(e.passthrough_extended, 1)
    assert.equal(e.passthrough_rewrite, 1)
    // protocol 4 + PORTAL_STREAM 2
    assert.equal(e.xproto_stream, 6)
    // protocol 1 + PORTAL_CHUNKED 3
    assert.equal(e.materialized, 4)
    assert.equal(e.n_a, 2)
    assert.equal(e.total, 16 + 2 + 7 + 3 + 1 + 1 + 6 + 4 + 2)
  })
})

describe('parseSqlCursorMetrics', () => {
  it('sums sql_cursor_* modes only', () => {
    const c = parseSqlCursorMetrics(SAMPLE)
    assert.equal(c.declare, 2)
    assert.equal(c.fetch, 5)
    assert.equal(c.close, 1)
    assert.equal(c.session_end, 1)
    assert.equal(c.unsupported, 3)
  })
})

describe('parsePortalResumeMetrics', () => {
  it('sums hold/resume_hold/logical_skip and ignores sql_cursor_*', () => {
    const r = parsePortalResumeMetrics(SAMPLE)
    assert.equal(r.hold, 9)
    assert.equal(r.resume_hold, 4)
    assert.equal(r.logical_skip, 2)
    assert.equal(r.total, 15)
  })
})

describe('parsePortalHttpMetrics', () => {
  it('splits PORTAL_STREAM vs PORTAL_CHUNKED and stream peak only', () => {
    const h = parsePortalHttpMetrics(SAMPLE)
    assert.equal(h.stream, 8)
    assert.equal(h.chunked, 3)
    assert.equal(h.total, 11)
    // stream peak ignores PORTAL_CHUNKED=50
    assert.equal(h.stream_peak_rows, 2)
  })
})

describe('parseSecurePathMetrics', () => {
  it('sums mask_rows and passthrough_bytes', () => {
    const s = parseSecurePathMetrics(SAMPLE)
    assert.equal(s.mask_rows, 15)
    assert.equal(s.passthrough_bytes, 2560)
  })
})
