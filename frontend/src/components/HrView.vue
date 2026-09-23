<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  overview: { type: Object, default: null },
  employees: { type: Array, default: () => [] },
  busy: Boolean,
  error: { type: Object, default: null },
  importing: Boolean,
  importResult: { type: Object, default: null },
  importError: { type: Object, default: null },
  refreshingAfterImport: Boolean,
})
const emit = defineEmits(['refresh', 'select-employee', 'import-files'])
const { t, te, locale } = useI18n()
const form = ref(null)
const files = ref({ employees: null, history: null })
const validation = ref(null)
const locked = computed(() => props.busy || props.importing || props.refreshingAfterImport)
const employeeNames = computed(() => new Map(props.employees.map(employee => [employee.employee_id, employee.full_name])))
const participationStatuses = computed(() => {
  const statuses = new Set(['completed', 'in_progress', 'dropped', 'no_show', 'declined', 'overdue'])
  for (const event of props.overview?.participation || []) {
    for (const status of Object.keys(event.by_status)) statuses.add(status)
  }
  return [...statuses]
})
const importCounts = [
  ['employees_added', 'employeesAdded'], ['employees_updated', 'employeesUpdated'],
  ['history_added', 'historyAdded'], ['history_unchanged', 'historyUnchanged'],
]

function percent(value) {
  return new Intl.NumberFormat(locale.value, { style: 'percent', maximumFractionDigits: 1 }).format(value)
}
function statusName(status) {
  return te(`hr.statuses.${status}`) ? t(`hr.statuses.${status}`) : status
}
function reasonText(reason) {
  return String(reason).split(':').map(part => part.trim().split(',').map(code => {
    const key = `hr.reasons.${code.trim()}`
    return te(key) ? t(key) : code.trim()
  }).join('; ')).join(': ')
}
function selectFile(kind, event) {
  files.value[kind] = event.target.files?.[0] || null
  validation.value = null
}
function submitImport() {
  if (locked.value) return
  validation.value = null
  if (!files.value.employees && !files.value.history) {
    validation.value = { key: 'importMissing' }
    return
  }
  for (const [kind, file] of Object.entries(files.value)) {
    if (!file) continue
    if (file.size > 5 * 1024 * 1024) {
      validation.value = { key: 'tooLarge', values: { name: file.name } }
      return
    }
    const extension = kind === 'employees' ? '.json' : '.csv'
    if (!file.name.toLowerCase().endsWith(extension)) {
      validation.value = { key: 'wrongType', values: { field: kind === 'employees' ? 'employees' : 'history', extension } }
      return
    }
  }
  emit('import-files', { ...files.value })
}
watch(() => props.importResult, result => {
  if (!result) return
  form.value?.reset()
  files.value = { employees: null, history: null }
  validation.value = null
})
</script>

<template>
  <div class="hr-view">
    <header class="hero-row">
      <div class="hero-copy">
        <p class="eyebrow">HR · CAREER QUEST</p>
        <h1>{{ t('hr.title') }}</h1>
        <p class="hero-subtitle">{{ t('hr.subtitle') }}</p>
      </div>
      <button class="outline-button" type="button" :disabled="locked" @click="emit('refresh')">{{ t('hr.refresh') }}</button>
    </header>

    <p v-if="busy" class="notice" role="status">{{ t('hr.loading') }}</p>
    <div v-if="error" class="hr-error" role="alert">
      <strong>{{ t('hr.loadError') }}</strong>
      <p>{{ error.message }}</p>
      <p v-if="overview">{{ t('hr.stale') }}</p>
    </div>

    <template v-if="overview">
      <div class="stats-grid hr-stats" :aria-busy="busy">
        <article class="stat-card"><p class="stat-label">{{ t('hr.employees') }}</p><p class="stat-value">{{ overview.employees_count }}</p></article>
        <article class="stat-card"><p class="stat-label">{{ t('hr.asOf') }}</p><p class="stat-value hr-date">{{ overview.as_of_date }}</p></article>
        <article class="stat-card"><p class="stat-label">{{ t('hr.version') }}</p><p class="stat-value">{{ overview.data_version }}</p></article>
      </div>
    </template>
    <p v-else-if="!busy && !error" class="empty-state">{{ t('hr.noOverview') }}</p>

    <section class="panel hr-import" aria-labelledby="hr-import-title">
      <h2 id="hr-import-title">{{ t('hr.importTitle') }}</h2>
      <p class="body-copy" id="hr-import-description">{{ t('hr.importDescription') }}</p>
      <form ref="form" @submit.prevent="submitImport" aria-describedby="hr-import-description" :aria-busy="importing">
        <fieldset :disabled="locked">
          <div class="hr-file-fields">
            <label for="hr-employees-file">{{ t('hr.employeesFile') }}
              <input id="hr-employees-file" type="file" accept=".json,application/json" aria-describedby="hr-employees-help" @change="selectFile('employees', $event)">
              <span id="hr-employees-help" class="hr-field-help">{{ t('hr.employeesHelp') }}</span>
            </label>
            <label for="hr-history-file">{{ t('hr.historyFile') }}
              <input id="hr-history-file" type="file" accept=".csv,text/csv" aria-describedby="hr-history-help" @change="selectFile('history', $event)">
              <span id="hr-history-help" class="hr-field-help">{{ t('hr.historyHelp') }}</span>
            </label>
          </div>
          <button type="submit" class="dark-button hr-import-button">{{ t(importing ? 'hr.importing' : 'hr.importSubmit') }}</button>
        </fieldset>
      </form>
      <p v-if="validation" class="hr-error" role="alert">{{ t(`hr.${validation.key}`, validation.values || {}) }}</p>
      <div v-if="importError" class="hr-error" role="alert"><strong>{{ t('hr.importError') }}</strong><p>{{ importError.message }}</p></div>
      <div v-if="importResult" class="notice hr-import-success" role="status">
        <strong>{{ t('hr.importSuccess') }}</strong>
        <dl class="hr-import-counts">
          <div v-for="[field, label] in importCounts" :key="field"><dt>{{ t(`hr.${label}`) }}</dt><dd>{{ importResult[field] }}</dd></div>
          <div><dt>{{ t('hr.version') }}</dt><dd>{{ importResult.data_version }}</dd></div>
        </dl>
        <template v-if="importResult.warnings?.length">
          <strong>{{ t('hr.warnings') }}</strong>
          <ul><li v-for="(warning, index) in importResult.warnings" :key="index">{{ warning }}</li></ul>
        </template>
        <p v-if="refreshingAfterImport">{{ t('hr.refreshing') }}</p>
        <p v-else-if="error">{{ t('hr.refreshFailed') }}</p>
      </div>
    </section>

    <template v-if="overview">
      <section class="panel" :aria-busy="busy" aria-labelledby="hr-gaps-title">
        <h2 id="hr-gaps-title">{{ t('hr.gaps') }}</h2>
        <p class="body-copy" id="hr-gaps-description">{{ t('hr.gapsDescription') }}</p>
        <div v-if="overview.skill_gaps.length" class="table-scroll" role="region" :aria-label="t('hr.gaps')" tabindex="0">
          <table aria-describedby="hr-gaps-description">
            <thead><tr><th scope="col">{{ t('hr.skill') }}</th><th scope="col">{{ t('hr.share') }}</th><th scope="col">{{ t('hr.people') }}</th><th scope="col">{{ t('hr.totalGap') }}</th><th scope="col">{{ t('hr.critical') }}<small>{{ t('hr.criticalHint') }}</small></th></tr></thead>
            <tbody><tr v-for="gap in overview.skill_gaps" :key="gap.skill_id">
              <th scope="row">{{ gap.name }}<small>{{ gap.skill_id }}</small></th>
              <td class="hr-percent">{{ percent(gap.gap_rate) }}</td><td>{{ gap.employees_with_gap }} / {{ gap.employees_requiring_skill }}</td><td>{{ gap.total_gap }}</td><td>{{ gap.critical_employee_count }}</td>
            </tr></tbody>
          </table>
        </div>
        <p v-else class="empty-state">{{ t('hr.noGaps') }}</p>
      </section>

      <section class="panel" :aria-busy="busy" aria-labelledby="hr-no-step-title">
        <h2 id="hr-no-step-title">{{ t('hr.withoutStep') }}</h2>
        <p class="body-copy">{{ t('hr.withoutStepDescription') }}</p>
        <ul v-if="overview.employees_without_step.length" class="hr-exceptions">
          <li v-for="employee in overview.employees_without_step" :key="employee.employee_id">
            <div><strong>{{ employeeNames.get(employee.employee_id) || employee.employee_id }}</strong><p class="hr-employee-id">{{ employee.employee_id }}</p><p>{{ reasonText(employee.reason) }}</p></div>
            <button class="outline-button" type="button" :disabled="locked" @click="emit('select-employee', employee.employee_id)">{{ t('hr.openProfile') }}</button>
          </li>
        </ul>
        <p v-else class="empty-state">{{ t('hr.noExceptions') }}</p>
      </section>

      <section class="panel" :aria-busy="busy" aria-labelledby="hr-participation-title">
        <h2 id="hr-participation-title">{{ t('hr.participation') }}</h2>
        <p class="body-copy" id="hr-participation-description">{{ t('hr.participationDescription') }}</p>
        <div v-if="overview.participation.length" class="table-scroll" role="region" :aria-label="t('hr.participation')" tabindex="0">
          <table aria-describedby="hr-participation-description" class="hr-participation-table">
            <thead><tr><th scope="col">{{ t('hr.event') }}</th><th scope="col">{{ t('hr.records') }}</th><th v-for="status in participationStatuses" :key="status" scope="col">{{ statusName(status) }}</th></tr></thead>
            <tbody><tr v-for="event in overview.participation" :key="event.event_id"><th scope="row">{{ event.title }}<small>{{ event.event_id }}</small></th><td>{{ event.total_records }}</td><td v-for="status in participationStatuses" :key="status">{{ event.by_status[status] ?? 0 }}</td></tr></tbody>
          </table>
        </div>
        <p v-else class="empty-state">{{ t('hr.noParticipation') }}</p>
      </section>
    </template>
  </div>
</template>

<style scoped>
.hr-view { display: grid; gap: 24px; }
.hr-view .hero-row, .hr-view .stats-grid { margin-bottom: 0; }
.hr-view .notice { margin-top: 0; }
.hr-stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.hr-stats .stat-card { min-height: 125px; }
.hr-date { font-size: 26px; }
.hr-import form { margin-top: 22px; }
.hr-import fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
.hr-file-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 22px; }
.hr-field-help { font-size: 15px; font-weight: 400; color: var(--muted); }
.hr-import-button { width: auto; }
.hr-import input[type=file] { font-size: 15px; padding: 12px; }
.hr-import input::file-selector-button { color: var(--green-dark); background: var(--green-light); padding: 8px 10px; border: 0; border-radius: 6px; cursor: pointer; margin-right: 10px; }
.hr-error { padding: 16px 20px; border: 1px solid #ebc2bc; background: #fff2ee; color: #83392c; border-radius: 12px; overflow-wrap: anywhere; }
.hr-import .hr-error, .hr-import .hr-import-success { margin-top: 20px; }
.hr-import-counts { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin: 16px 0; }
.hr-import-counts dt { color: var(--muted); }
.hr-import-counts dd { margin: 0; font-size: 24px; font-weight: 700; color: var(--green-dark); }
.hr-view th { font-size: 15px; letter-spacing: 0; }
.hr-view tbody th { color: var(--ink); background: transparent; font-size: 16px; }
.hr-view th small { display: block; color: var(--muted); font-size: 14px; font-weight: 400; margin-top: 5px; }
.hr-view td { font-variant-numeric: tabular-nums; }
.hr-percent { color: var(--green-dark); font-weight: 700; white-space: nowrap; }
.hr-exceptions { list-style: none; padding: 0; margin: 22px 0 0; display: grid; gap: 0; }
.hr-exceptions li { padding: 22px 0; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.hr-exceptions li:first-child { padding-top: 0; }
.hr-exceptions li:last-child { border: 0; padding-bottom: 0; }
.hr-exceptions li > div { min-width: 0; overflow-wrap: anywhere; }
.hr-exceptions li > button { flex-shrink: 0; }
.hr-exceptions li p { margin-top: 8px; }
.hr-employee-id { font-size: 14px; color: var(--muted); }
.hr-participation-table { min-width: 950px; }
.hr-participation-table tbody th { min-width: 240px; }
@media (max-width: 700px) {
  .hr-stats, .hr-file-fields { grid-template-columns: 1fr; }
  .hr-view .hero-row, .hr-exceptions li { flex-direction: column; align-items: stretch; }
  .hr-stats .stat-card { min-height: 105px; }
  .hr-import-button { width: 100%; }
  .hr-view .panel { padding: 20px; }
}
</style>
