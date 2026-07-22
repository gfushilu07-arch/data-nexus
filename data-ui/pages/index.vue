<script setup lang="ts">
import type {
  AdminAuditStats,
  AdminEndpoint,
  AdminListener,
  AdminPool,
  AdminSecurityPolicies,
  AdminService,
  AdminSession,
  AdminTicket,
  AdminVaultLease,
  EncodePeakMetrics,
  ExecutePathMetrics,
  PortalHttpMetrics,
  PortalResumeMetrics,
  SecurePathMetrics,
  SqlCursorMetricModes,
} from '~/composables/useAdminApi'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Overview · Data Nexus Admin' })

const api = useAdminApi()
const { apiBase, hydrate: hydrateSettings } = useAdminSettings()

const version = ref('—')
const status = ref('')
const statusKind = ref<'ok' | 'error' | ''>('')
const listeners = ref<AdminListener[]>([])
const services = ref<AdminService[]>([])
const endpoints = ref<AdminEndpoint[]>([])
const pools = ref<AdminPool[]>([])
const sessions = ref<AdminSession[]>([])
const auditStats = ref<AdminAuditStats | null>(null)
const policies = ref<AdminSecurityPolicies | null>(null)
const tickets = ref<AdminTicket[]>([])
const leases = ref<AdminVaultLease[]>([])
const sqlCursors = ref<SqlCursorMetricModes | null>(null)
const portalResume = ref<PortalResumeMetrics | null>(null)
const portalHttp = ref<PortalHttpMetrics | null>(null)
const securePath = ref<SecurePathMetrics | null>(null)
const encodePeak = ref<EncodePeakMetrics | null>(null)
const executePaths = ref<ExecutePathMetrics | null>(null)

function setStatus(msg: string, kind: 'ok' | 'error' | '' = '') {
  status.value = msg
  statusKind.value = kind
}

function isLeaseExpired(l: AdminVaultLease) {
  return Date.now() > (l.expires_at_unix_ms || 0)
}

const ticketCounts = computed(() => {
  const c = { pending: 0, active: 0, rejected: 0, total: tickets.value.length }
  for (const t of tickets.value) {
    const s = (t.status || '').toLowerCase()
    if (s === 'pending')
      c.pending++
    else if (s === 'active')
      c.active++
    else if (s === 'rejected')
      c.rejected++
  }
  return c
})

const leaseCounts = computed(() => {
  const c = { active: 0, expired: 0, revoked: 0, total: leases.value.length }
  for (const l of leases.value) {
    if (l.revoked)
      c.revoked++
    else if (isLeaseExpired(l))
      c.expired++
    else c.active++
  }
  return c
})

const protocolSessionBits = computed(() => {
  const m: Record<string, number> = {}
  for (const s of sessions.value) {
    const k = (s.frontend_protocol || '?').toLowerCase()
    m[k] = (m[k] || 0) + 1
  }
  return Object.entries(m)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([p, n]) => `${p}=${n}`)
    .join(' ')
})

const securityEnabled = computed(() => policies.value?.enabled === true)
const pdpBackend = computed(() => policies.value?.pdp_backend || policies.value?.pdp?.backend || '—')
const auditLevel = computed(() => policies.value?.default_audit_level || '—')
const windowRows = computed(() => policies.value?.streaming?.window_rows)
const stateBackend = computed(() => policies.value?.state?.backend || '—')
const auditSample = computed(() => policies.value?.audit_sample || null)

async function loadAll() {
  setStatus('Loading…')
  const base = apiBase.value
  try {
    const [ver, ls, svcs, eps, pls, sess, astats, pol, tix, vls, metricsTxt] = await Promise.all([
      api.version(base).catch(() => 'Data Nexus'),
      api.listeners(base),
      api.services(base),
      api.endpoints(base),
      api.pools(base).catch(() => [] as AdminPool[]),
      api.sessions(base),
      api.auditStats(base).catch(() => null),
      api.securityPolicies(base).catch(() => null),
      api.tickets(100, base).catch(() => [] as AdminTicket[]),
      api.vaultLeases(base).catch(() => [] as AdminVaultLease[]),
      api.metricsText(base).catch(() => null as string | null),
    ])
    version.value = String(ver || 'Data Nexus').trim()
    listeners.value = ls
    services.value = svcs
    endpoints.value = eps
    pools.value = pls
    sessions.value = sess
    auditStats.value = astats
    policies.value = pol
    tickets.value = tix
    leases.value = vls
    if (metricsTxt) {
      sqlCursors.value = api.parseSqlCursorMetrics(metricsTxt)
      portalResume.value = api.parsePortalResumeMetrics(metricsTxt)
      portalHttp.value = api.parsePortalHttpMetrics(metricsTxt)
      securePath.value = api.parseSecurePathMetrics(metricsTxt)
      encodePeak.value = api.parseEncodePeakMetrics(metricsTxt)
      executePaths.value = api.parseExecutePathMetrics(metricsTxt)
    }
    else {
      sqlCursors.value = null
      portalResume.value = null
      portalHttp.value = null
      securePath.value = null
      encodePeak.value = null
      executePaths.value = null
    }
    const secBit = pol
      ? ` · security=${pol.enabled ? 'on' : 'off'} pdp=${pol.pdp_backend || '—'}`
      : ''
    const sessBit = protocolSessionBits.value ? ` · ${protocolSessionBits.value}` : ''
    setStatus(`Updated ${new Date().toLocaleTimeString()}${secBit}${sessBit}`, 'ok')
  }
  catch (err: any) {
    setStatus(err?.data?.message || err?.message || String(err), 'error')
  }
}

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  hydrateSettings()
  loadAll()
  timer = setInterval(loadAll, 15000)
})
onUnmounted(() => {
  if (timer)
    clearInterval(timer)
})
</script>

<template>
  <div class="page">
    <div class="page-toolbar">
      <div>
        <h2 class="page-title">
          Overview
        </h2>
        <div class="meta">
          {{ version }}
        </div>
      </div>
      <button
        type="button"
        class="btn"
        @click="loadAll"
      >
        Refresh
      </button>
    </div>

    <div
      class="status-line"
      :class="statusKind"
    >
      {{ status }}
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="label">
          Listeners
        </div>
        <div class="value">
          {{ listeners.length }}
        </div>
      </div>
      <div class="stat-card">
        <div class="label">
          Services
        </div>
        <div class="value">
          {{ services.length }}
        </div>
      </div>
      <div class="stat-card">
        <div class="label">
          Endpoints
        </div>
        <div class="value">
          {{ endpoints.length }}
        </div>
      </div>
      <div class="stat-card">
        <div class="label">
          Sessions
        </div>
        <div class="value">
          {{ sessions.length }}
        </div>
        <div
          v-if="protocolSessionBits"
          class="sub"
        >
          {{ protocolSessionBits }}
        </div>
      </div>
      <div class="stat-card">
        <div class="label">
          Pools
        </div>
        <div class="value">
          {{ pools.length }}
        </div>
      </div>
    </div>

    <h3 class="section-title">
      Security &amp; ops
      <span class="section-hint">UI28 · soft-fail if endpoints unavailable</span>
    </h3>
    <div class="stat-grid">
      <NuxtLink
        class="stat-card link-card"
        to="/policies"
      >
        <div class="label">
          Security
        </div>
        <div class="value">
          <span
            class="pill"
            :class="securityEnabled ? 'on' : 'off'"
          >{{ securityEnabled ? 'on' : 'off' }}</span>
        </div>
        <div class="sub mono">
          pdp={{ pdpBackend }}
          · audit={{ auditLevel }}
          <template v-if="windowRows != null">
            · window_rows={{ windowRows }}
          </template>
          · state={{ stateBackend }}
          <template v-if="stateBackend === 'file'">
            · last-writer-wins / crdt=false / vault_password_zeroize (not CRDT; not mlock)
          </template>
        </div>
      </NuxtLink>
      <div
        v-if="sqlCursors"
        class="stat-card"
      >
        <div class="label">
          SQL cursors (process-local)
        </div>
        <div class="value mono">
          d={{ sqlCursors.declare }}
          · f={{ sqlCursors.fetch }}
          · c={{ sqlCursors.close }}
        </div>
        <div class="sub mono">
          session_end={{ sqlCursors.session_end }}
          <template v-if="sqlCursors.unsupported">
            · unsupported={{ sqlCursors.unsupported }}
          </template>
          · not backend WITH HOLD
          · <a
            class="inline-link"
            :href="`${apiBase}/metrics`"
            target="_blank"
            rel="noreferrer"
          >/metrics</a>
        </div>
      </div>
      <div
        v-if="portalResume && portalResume.total > 0"
        class="stat-card"
      >
        <div class="label">
          Portal resume (A10)
        </div>
        <div class="value mono">
          hold={{ portalResume.hold + portalResume.resume_hold }}
          · skip={{ portalResume.logical_skip }}
        </div>
        <div class="sub mono">
          hold={{ portalResume.hold }}
          · resume_hold={{ portalResume.resume_hold }}
          · logical_skip={{ portalResume.logical_skip }}
          · prefer RowStream hold; skip re-runs SQL
          · not backend WITH HOLD
          · <a
            class="inline-link"
            :href="`${apiBase}/metrics`"
            target="_blank"
            rel="noreferrer"
          >/metrics</a>
        </div>
      </div>
      <div
        v-if="portalHttp && portalHttp.total > 0"
        class="stat-card"
      >
        <div class="label">
          Portal HTTP (A09)
        </div>
        <div class="value mono">
          stream={{ portalHttp.stream }}
          · chunked={{ portalHttp.chunked }}
        </div>
        <div class="sub mono">
          PORTAL_STREAM={{ portalHttp.stream }}
          · PORTAL_CHUNKED={{ portalHttp.chunked }}
          <template v-if="portalHttp.stream_peak_rows > 0">
            · stream_peak_rows={{ portalHttp.stream_peak_rows }}
          </template>
          · stream=backend_window; chunked may materialize backend
          · peak logical only
          · <a
            class="inline-link"
            :href="`${apiBase}/metrics`"
            target="_blank"
            rel="noreferrer"
          >/metrics</a>
        </div>
      </div>
      <div
        v-if="securePath && (securePath.mask_rows > 0 || securePath.passthrough_bytes > 0)"
        class="stat-card"
      >
        <div class="label">
          Secure path (O01/A05)
        </div>
        <div class="value mono">
          mask_rows={{ securePath.mask_rows }}
        </div>
        <div class="sub mono">
          passthrough_bytes={{ securePath.passthrough_bytes }}
          · mask_rows = non-empty mask obligation only
          · wire bytes on passthrough — not RSS proof
          · <a
            class="inline-link"
            :href="`${apiBase}/metrics`"
            target="_blank"
            rel="noreferrer"
          >/metrics</a>
        </div>
      </div>
      <div
        v-if="encodePeak && (encodePeak.encode_windows > 0 || encodePeak.peak_window_rows > 0)"
        class="stat-card"
      >
        <div class="label">
          Encode peak (A06 logical)
        </div>
        <div class="value mono">
          peak_rows={{ encodePeak.peak_window_rows }}
        </div>
        <div class="sub mono">
          peak_bytes={{ encodePeak.peak_window_bytes }}
          · windows={{ encodePeak.encode_windows }}
          · encode_bytes={{ encodePeak.encode_bytes }}
          · not process RSS
          · <a
            class="inline-link"
            :href="`${apiBase}/metrics`"
            target="_blank"
            rel="noreferrer"
          >/metrics</a>
        </div>
      </div>
      <div
        v-if="executePaths && executePaths.total > 0"
        class="stat-card"
      >
        <div class="label">
          Execute paths (A05/A08)
        </div>
        <div class="value mono">
          stream={{ executePaths.streaming + executePaths.streaming_demote }}
          · pass={{ executePaths.passthrough + executePaths.passthrough_client + executePaths.passthrough_extended + executePaths.passthrough_rewrite }}
        </div>
        <div class="sub mono">
          streaming={{ executePaths.streaming }}
          · demote={{ executePaths.streaming_demote }}
          · passthrough={{ executePaths.passthrough }}
          · client={{ executePaths.passthrough_client }}
          · ext={{ executePaths.passthrough_extended + executePaths.passthrough_rewrite }}
          · xproto={{ executePaths.xproto_stream }}
          · mat/n-a={{ executePaths.materialized + executePaths.n_a }}
          · total={{ executePaths.total }}
          · counters only (not RSS proof)
        </div>
      </div>
      <NuxtLink
        class="stat-card link-card"
        to="/audit"
      >
        <div class="label">
          Audit accepted
        </div>
        <div class="value">
          {{ auditStats?.accepted ?? '—' }}
        </div>
        <div class="sub mono">
          written={{ auditStats?.written ?? '—' }}
          · dropped={{ auditStats?.dropped ?? '—' }}
          · prio_acc={{ auditStats?.priority_accepted ?? '—' }}
        </div>
      </NuxtLink>
      <NuxtLink
        class="stat-card link-card"
        to="/policies"
      >
        <div class="label">
          Audit sample (B08)
        </div>
        <div class="value mono">
          <template v-if="auditSample">
            {{ auditSample.sample_enabled ? 'on' : 'off' }}
          </template>
          <template v-else>
            —
          </template>
        </div>
        <div
          v-if="auditSample"
          class="sub mono"
        >
          max_rows={{ auditSample.sample_max_rows }}
          · max_bytes={{ auditSample.sample_max_bytes }}
          · needs {{ auditSample.requires_audit_level || 'L2' }}
          · full_result_l3={{ auditSample.full_result_l3 ?? false }}
          · not L3 full archive
        </div>
      </NuxtLink>
      <NuxtLink
        class="stat-card link-card"
        to="/audit"
      >
        <div class="label">
          Audit index
        </div>
        <div class="value">
          {{ auditStats?.index_rows ?? '—' }}
        </div>
        <div class="sub mono">
          enabled={{ auditStats?.index_enabled ?? '—' }}
          · inserted={{ auditStats?.index_inserted ?? '—' }}
          · errors={{ auditStats?.index_errors ?? '—' }}
        </div>
      </NuxtLink>
      <NuxtLink
        class="stat-card link-card"
        to="/tickets"
      >
        <div class="label">
          Tickets
        </div>
        <div class="value">
          {{ ticketCounts.total }}
        </div>
        <div class="sub mono">
          pending={{ ticketCounts.pending }}
          · active={{ ticketCounts.active }}
          · rejected={{ ticketCounts.rejected }}
        </div>
      </NuxtLink>
      <NuxtLink
        class="stat-card link-card"
        to="/vault"
      >
        <div class="label">
          Vault leases
        </div>
        <div class="value">
          {{ leaseCounts.total }}
        </div>
        <div class="sub mono">
          active={{ leaseCounts.active }}
          · expired={{ leaseCounts.expired }}
          · revoked={{ leaseCounts.revoked }}
        </div>
      </NuxtLink>
    </div>

    <section class="card">
      <h2>Quick links</h2>
      <div class="admin-actions">
        <NuxtLink
          class="btn"
          to="/topology"
        >
          Topology
        </NuxtLink>
        <NuxtLink
          class="btn"
          to="/sessions"
        >
          Sessions
        </NuxtLink>
        <NuxtLink
          class="btn"
          to="/portal"
        >
          SQL Portal
        </NuxtLink>
        <NuxtLink
          class="btn"
          to="/audit"
        >
          Audit
        </NuxtLink>
        <NuxtLink
          class="btn"
          to="/tickets"
        >
          Tickets
        </NuxtLink>
        <NuxtLink
          class="btn"
          to="/vault"
        >
          Vault
        </NuxtLink>
        <NuxtLink
          class="btn"
          to="/policies"
        >
          Policies
        </NuxtLink>
        <NuxtLink
          class="btn"
          to="/cedar"
        >
          Cedar
        </NuxtLink>
        <NuxtLink
          class="btn"
          to="/settings"
        >
          Settings / Reload
        </NuxtLink>
      </div>
    </section>
  </div>
</template>

<style scoped>
.section-title {
  margin: 1rem 0 .5rem;
  font-size: 1rem;
  font-weight: 600;
  color: #24292f;
  display: flex;
  align-items: baseline;
  gap: .5rem;
}
.section-hint {
  font-size: .78rem;
  font-weight: 400;
  color: #6b7280;
}
.stat-card .sub {
  margin-top: .35rem;
  font-size: .75rem;
  color: #57606a;
  line-height: 1.35;
  word-break: break-word;
}
.stat-card .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.link-card {
  text-decoration: none;
  color: inherit;
  transition: border-color .12s ease, box-shadow .12s ease;
}
.link-card:hover {
  border-color: #0969da;
  box-shadow: 0 0 0 1px rgba(9, 105, 218, .15);
}
.pill {
  display: inline-block;
  padding: .1rem .45rem;
  border-radius: 999px;
  font-size: .85rem;
  font-weight: 600;
}
.pill.on { background: #dafbe1; color: #1a7f37; }
.pill.off { background: #eef1f4; color: #57606a; }
.inline-link { color: #0969da; text-decoration: none; }
.inline-link:hover { text-decoration: underline; }
</style>
