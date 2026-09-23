<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from './AppIcon.vue'
import RecommendationCard from './RecommendationCard.vue'

const props = defineProps({
  profile: { type: Object, required: true },
  recommendations: { type: Object, default: null },
  events: { type: Array, default: () => [] },
  skills: { type: Array, default: () => [] },
  loadingRecommendations: Boolean,
  recommendationError: { type: Object, default: null },
  completion: { type: Object, default: () => ({ busy: false, pending: null, error: null, result: null }) },
})
defineEmits(['refresh', 'complete', 'retry-completion', 'discard-completion'])
const { t, te, locale } = useI18n()
const person = computed(() => props.profile.employee)
const target = computed(() => props.profile.trajectory)
const initials = computed(() => (person.value.full_name || '').trim().split(/\s+/).slice(0, 2).map(part => part[0]).join(''))
const eventMap = computed(() => new Map(props.events.map(event => [event.event_id, event])))
const skillMap = computed(() => new Map(props.skills.map(skill => [skill.skill_id, skill.name])))
const currentSkills = computed(() => Object.entries(props.profile.effective_skills).map(([id, level]) => ({ id, level, name: skillMap.value.get(id) || id })))
const history = computed(() => [...props.profile.history].sort((a, b) => b.date.localeCompare(a.date) || b.record_id.localeCompare(a.record_id)))
const blocked = computed(() => props.completion.busy || Boolean(props.completion.pending))
function number(value) { return new Intl.NumberFormat(locale.value, { maximumFractionDigits: 2 }).format(value) }
function date(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(`${value.slice(0, 10)}T00:00:00Z`))
}
function label(group, value) { return te(`employee.${group}.${value}`) ? t(`employee.${group}.${value}`) : value || '—' }
</script>

<template>
  <div class="employee-workspace">
    <section class="hero-row">
      <div><p class="eyebrow">Career Quest</p><h1>{{ t('employee.title') }}</h1><p class="hero-subtitle">{{ t('employee.intro') }}</p></div>
      <p class="snapshot-label">{{ t('employee.snapshot', { date: date(profile.as_of_date) }) }}</p>
    </section>

    <section class="panel employee-profile" :aria-label="t('employee.profile')">
      <div class="avatar employee-avatar" aria-hidden="true">{{ initials }}</div>
      <div class="employee-identity"><p class="section-kicker">{{ person.employee_id }}</p><h2>{{ person.full_name }}</h2><p>{{ person.role }} · {{ person.grade }}</p></div>
      <span class="skill-tag employee-department">{{ person.department }}</span>
      <dl class="employee-facts">
        <div><dt>{{ t('employee.role') }}</dt><dd>{{ person.role }}</dd></div>
        <div><dt>{{ t('employee.grade') }}</dt><dd>{{ person.grade }}</dd></div>
        <div><dt>{{ t('employee.tenure') }}</dt><dd>{{ t('employee.months', { count: person.tenure_months }) }}</dd></div>
        <div><dt>{{ t('employee.workFormat') }}</dt><dd>{{ label('formats', person.work_format) }}</dd></div>
      </dl>
    </section>

    <div class="employee-target-grid">
      <section class="panel goal-panel">
        <div class="panel-heading"><p class="section-kicker">{{ t('employee.target') }}</p><AppIcon name="target" /></div>
        <h2>{{ target.target_role }} · {{ target.target_grade }}</h2>
        <p class="body-copy">{{ label('targetSource', target.target_source) }}</p>
        <div class="goal-progress"><strong>{{ number(target.progress_pct) }}<span>%</span></strong><span>{{ t('employee.coverage') }}</span></div>
        <progress class="coverage-progress" :value="target.progress_pct" max="100" :aria-label="t('employee.coverage')" />
        <p class="body-copy">{{ target.note }}</p>
      </section>
      <div class="employee-target-stats">
        <div class="stat-card"><div class="stat-top"><span class="stat-icon gold"><AppIcon name="target" /></span><span class="stat-label">{{ t('employee.criticalGaps') }}</span></div><p class="stat-value">{{ target.critical_gaps }}</p></div>
        <div class="stat-card"><div class="stat-top"><span class="stat-icon"><AppIcon name="book" /></span><span class="stat-label">{{ t('employee.remainingGap') }}</span></div><p class="stat-value">{{ target.remaining_gap }}</p></div>
      </div>
    </div>

    <section v-if="completion.busy" class="notice completion-notice" role="status" aria-live="polite">{{ t('employee.saving') }}</section>
    <p v-if="completion.error && !completion.pending && !completion.busy" class="notice completion-error" role="alert">{{ completion.error.message }}</p>
    <section v-if="completion.pending && !completion.busy" class="panel completion-pending" role="alert">
      <h2>{{ t('employee.pending') }}</h2>
      <p class="body-copy">{{ t(completion.pending.retryable ? 'employee.pendingNote' : 'employee.pendingRejected') }}</p>
      <p v-if="completion.error" class="completion-error">{{ completion.error.message }}</p>
      <div class="completion-actions">
        <button v-if="completion.pending.retryable" type="button" class="outline-button" @click="$emit('retry-completion')">{{ t('employee.retry') }}</button>
        <button type="button" class="outline-button" @click="$emit('discard-completion')">{{ t('employee.discard') }}</button>
      </div>
      <p class="completion-help">{{ t('employee.discardNote') }}</p>
    </section>
    <section v-if="completion.result" class="panel completion-success" role="status" aria-live="polite">
      <div class="panel-heading"><h2>{{ t('employee.completed') }}</h2><AppIcon name="check" /></div>
      <p class="body-copy">{{ t('employee.completedEvent', { title: eventMap.get(completion.result.event_id)?.title || completion.result.event_id }) }}</p>
      <p v-if="completion.result.already_applied" class="notice">{{ t('employee.alreadyApplied') }}</p>
      <p class="body-copy">{{ t('employee.newCoverage') }}: <strong>{{ number(completion.result.trajectory.progress_pct) }}%</strong></p>
      <h3>{{ t('employee.actualChanges') }}</h3>
      <ul v-if="completion.result.skill_deltas.length" class="completion-deltas">
        <li v-for="delta in completion.result.skill_deltas" :key="delta.skill_id"><span>{{ skillMap.get(delta.skill_id) || delta.skill_id }}</span><strong>{{ delta.before }} → {{ delta.after }} (+{{ delta.delta }})</strong></li>
      </ul>
      <p v-else class="body-copy">{{ t('employee.noSkillChanges') }}</p>
    </section>

    <section class="employee-recommendations" aria-labelledby="recommendations-title" :aria-busy="loadingRecommendations">
      <div class="section-toolbar"><h2 id="recommendations-title">{{ t('employee.recommendations') }}</h2><button class="outline-button" type="button" :disabled="blocked || loadingRecommendations" @click="$emit('refresh')">{{ t('employee.refresh') }}</button></div>
      <p class="body-copy independent-note">{{ t('employee.independent') }}</p>
      <div v-if="loadingRecommendations" class="panel empty-state" role="status">{{ t('employee.loading') }}</div>
      <div v-else-if="recommendationError" class="panel" role="alert"><h3>{{ t('employee.recommendationError') }}</h3><p class="body-copy">{{ recommendationError.message }}</p></div>
      <template v-else-if="recommendations">
        <div class="recommendation-mode" :class="{ 'fallback-mode': recommendations.mode === 'fallback' }" role="status">
          <AppIcon :name="recommendations.mode === 'fallback' ? 'help' : 'check'" />
          <div><strong>{{ t(recommendations.mode === 'fallback' ? 'employee.fallback' : 'employee.llm') }}</strong><p v-if="recommendations.mode === 'fallback' && recommendations.fallback_reason">{{ t('employee.fallbackReason', { reason: recommendations.fallback_reason }) }}</p></div>
        </div>
        <div v-if="recommendations.steps.length" class="recommendation-grid">
          <RecommendationCard v-for="step in recommendations.steps" :key="`${profile.employee.employee_id}-${recommendations.data_version}-${step.event_id}`" :step="step" :event="eventMap.get(step.event_id)" :skills="skills" :history="profile.history" :as-of-date="profile.as_of_date" :disabled="blocked" @complete="$emit('complete', $event)" />
        </div>
        <div v-else class="panel empty-state"><h3>{{ t('employee.noSteps') }}</h3><p>{{ recommendations.no_step_reason || t('employee.noStepsHelp') }}</p></div>
      </template>
      <div v-else class="panel empty-state">{{ t('employee.noRecommendations') }}</div>
    </section>

    <section class="panel" aria-labelledby="requirements-title">
      <div class="panel-heading"><h2 id="requirements-title">{{ t('employee.requirements') }}</h2><span class="skill-tag">{{ target.target_grade }}</span></div>
      <div v-if="target.gaps.length" class="table-scroll">
        <table><thead><tr><th scope="col">{{ t('employee.skill') }}</th><th scope="col">{{ t('employee.current') }}</th><th scope="col">{{ t('employee.required') }}</th><th scope="col">{{ t('employee.gap') }}</th><th scope="col">{{ t('employee.priority') }}</th></tr></thead>
          <tbody><tr v-for="gap in target.gaps" :key="gap.skill_id" :class="{ 'critical-row': gap.critical && gap.gap > 0 }"><th scope="row">{{ gap.name }}</th><td>{{ gap.current }}</td><td>{{ gap.required }}</td><td>{{ gap.gap }}</td><td><span class="priority-badge" :class="{ critical: gap.critical }">{{ t(gap.critical ? 'employee.critical' : 'employee.regular') }}</span></td></tr></tbody>
        </table>
      </div>
      <p v-else class="empty-state">{{ t('employee.noRequirements') }}</p>
    </section>

    <section class="panel">
      <details class="current-skill-details">
        <summary>{{ t('employee.skills') }}</summary>
        <p class="body-copy">{{ t('employee.skillsNote') }} {{ t('employee.lastReview') }}: {{ date(person.last_review_date) }}</p>
        <div v-if="currentSkills.length" class="effective-skills-grid">
          <div v-for="skill in currentSkills" :key="skill.id" class="effective-skill"><strong>{{ skill.name }}</strong><span :aria-label="t('employee.level', { value: skill.level })">{{ skill.level }} / 5</span></div>
        </div>
        <p v-else class="empty-state">{{ t('employee.noSkills') }}</p>
      </details>
    </section>

    <section class="panel" aria-labelledby="history-title">
      <h2 id="history-title">{{ t('employee.history') }}</h2>
      <p class="body-copy">{{ t('employee.historyNote') }}</p>
      <div v-if="history.length" class="table-scroll">
        <table><thead><tr><th scope="col">{{ t('employee.event') }}</th><th scope="col">{{ t('employee.date') }}</th><th scope="col">{{ t('employee.status') }}</th><th scope="col">{{ t('employee.participationProgress') }}</th></tr></thead>
          <tbody><tr v-for="record in history" :key="record.record_id"><th scope="row">{{ eventMap.get(record.event_id)?.title || record.event_id }}<small>{{ record.record_id }}</small></th><td class="history-date">{{ date(record.date) }}</td><td><span class="history-status" :class="`status-${record.status}`">{{ label('statusLabels', record.status) }}</span></td><td>{{ record.completion_pct !== '' && record.completion_pct != null ? `${record.completion_pct}%` : '—' }}</td></tr></tbody>
        </table>
      </div>
      <p v-else class="empty-state">{{ t('employee.noHistory') }}</p>
    </section>
  </div>
</template>

<style scoped>
.employee-workspace { display: grid; gap: 24px; }
.employee-workspace .hero-row { margin: 0; }
.snapshot-label { color: var(--muted); font-size: 15px; }
.employee-profile { display: flex; flex-wrap: wrap; align-items: center; gap: 20px; }
.employee-avatar { width: 70px; height: 70px; font-size: 24px; flex-shrink: 0; }
.employee-identity h2 { font-size: 26px; margin-bottom: 8px; }
.employee-identity p:last-child { color: var(--muted); }
.employee-department { margin-left: auto; font-size: 14px; }
.employee-workspace .section-kicker, .employee-workspace .eyebrow { font-size: 14px; }
.employee-facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 20px; width: 100%; padding-top: 22px; border-top: 1px solid var(--line); }
.employee-facts dt { font-size: 14px; color: var(--muted); margin-bottom: 7px; }
.employee-facts dd { margin: 0; font-size: 16px; font-weight: 600; overflow-wrap: anywhere; }
.employee-target-grid { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 24px; }
.employee-target-grid .goal-panel h2 { max-width: none; }
.employee-target-stats { display: grid; gap: 16px; }
.employee-target-stats .stat-card { min-height: auto; }
.coverage-progress { width: 100%; height: 9px; border: 0; border-radius: 8px; overflow: hidden; accent-color: var(--green); margin-top: 14px; }
.coverage-progress::-webkit-progress-bar { background: #cde5d8; border-radius: 8px; }
.coverage-progress::-webkit-progress-value { background: var(--green); border-radius: 8px; }
.coverage-progress::-moz-progress-bar { background: var(--green); border-radius: 8px; }
.employee-recommendations .section-toolbar { margin-bottom: 0; }
.independent-note { margin: 14px 0 18px; }
.recommendation-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 310px), 1fr)); gap: 18px; }
.recommendation-mode { display: flex; align-items: flex-start; gap: 12px; padding: 18px; background: var(--green-light); border: 1px solid #d5e6db; border-radius: 12px; margin-bottom: 18px; font-size: 15px; line-height: 1.6; }
.recommendation-mode .shell-icon { flex-shrink: 0; margin-top: 3px; }
.recommendation-mode p { margin-top: 5px; overflow-wrap: anywhere; }
.fallback-mode { background: #fff8df; border-color: #e9d99f; color: #695013; }
.employee-workspace th { font-size: 14px; }
.employee-workspace tbody th { background: transparent; font-size: 16px; font-weight: 500; color: var(--ink); }
.employee-workspace th small { display: block; font-size: 14px; color: var(--muted); margin-top: 5px; }
.critical-row { background: #fffbef; }
.priority-badge, .history-status { display: inline-block; font-size: 14px; padding: 5px 9px; border-radius: 7px; white-space: nowrap; background: #eef3ef; color: #466050; }
.priority-badge.critical { background: #fff0bf; color: #6b521b; }
.history-date { white-space: nowrap; }
.status-completed { background: #e5f4eb; color: #126744; }
.status-in_progress { background: #e7f1fb; color: #275f91; }
.current-skill-details summary { font-size: 21px; font-weight: 600; cursor: pointer; }
.effective-skills-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 28px; margin-top: 18px; }
.effective-skill { display: flex; justify-content: space-between; gap: 15px; border-bottom: 1px solid var(--line); padding: 15px 0; font-size: 16px; }
.effective-skill strong { font-weight: 500; }
.effective-skill span { white-space: nowrap; font-weight: 700; color: var(--green-dark); }
.completion-notice { margin: 0; }
.completion-pending { background: #fffbef; border-color: #e9d99f; }
.completion-error { margin-top: 14px; color: #943321; overflow-wrap: anywhere; }
.completion-actions { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 18px; }
.completion-help { margin-top: 14px; font-size: 14px; line-height: 1.65; color: var(--muted); }
.completion-success { border-color: #acd6bd; background: #f3faf6; }
.completion-success h3 { margin-top: 18px; font-size: 17px; }
.completion-deltas { display: flex; flex-wrap: wrap; gap: 12px; list-style: none; margin: 14px 0 0; padding: 0; }
.completion-deltas li { display: grid; gap: 6px; padding: 14px; background: white; border: 1px solid var(--line); border-radius: 10px; }
.completion-deltas strong { color: var(--green-dark); }
@media (max-width: 760px) {
  .employee-target-grid { grid-template-columns: 1fr; }
  .employee-target-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .employee-facts { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .employee-department { margin-left: 0; }
  .effective-skills-grid { grid-template-columns: 1fr; }
}
@media (max-width: 480px) {
  .employee-target-stats { grid-template-columns: 1fr; }
  .employee-avatar { width: 55px; height: 55px; }
  .employee-identity { flex: 1; min-width: 180px; }
  .employee-identity h2 { font-size: 22px; }
}
</style>
