<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from './AppIcon.vue'

const props = defineProps({
  step: { type: Object, required: true },
  event: { type: Object, default: null },
  history: { type: Array, default: () => [] },
  skills: { type: Array, default: () => [] },
  asOfDate: { type: String, required: true },
  disabled: Boolean,
})
const emit = defineEmits(['complete'])
const { t, te, locale } = useI18n()
const selection = ref('')
const skillNames = computed(() => new Map(props.skills.map(skill => [skill.skill_id, skill.name])))
const rows = computed(() => props.history.filter(row => row.event_id === props.step.event_id))
// These are explicit participation/session inputs, not a second recommendation engine.
// The server remains responsible for eligibility, gains and completion validation.
const options = computed(() => {
  const ongoing = rows.value.filter(row => row.status === 'in_progress')
  const result = ongoing.filter(row => row.date <= props.asOfDate).map(row => ({
    key: `record:${row.record_id}`, record: row.record_id, session: null,
    label: t('employee.ongoing', { date: date(row.date), id: row.record_id }),
  }))
  if (props.step.format === 'self_paced') {
    if (!ongoing.length && props.step.event_id !== 'EV_036') {
      result.push({ key: 'self_paced', record: null, session: null, label: t('employee.selfPaced') })
    }
    return result
  }
  for (const session of props.event?.upcoming_sessions || []) {
    if (session <= props.asOfDate && !rows.value.some(row => row.date === session)) {
      result.push({ key: `session:${session}`, record: null, session, label: t('employee.session', { date: date(session) }) })
    }
  }
  return result
})
watch(options, values => {
  if (!values.some(option => option.key === selection.value)) selection.value = values.length === 1 ? values[0].key : ''
}, { immediate: true })
const selected = computed(() => options.value.find(option => option.key === selection.value))
function date(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(`${value.slice(0, 10)}T00:00:00Z`))
}
function number(value) { return new Intl.NumberFormat(locale.value, { maximumFractionDigits: 2 }).format(value) }
function format(value) { return te(`employee.formats.${value}`) ? t(`employee.formats.${value}`) : value }
function complete() {
  if (!selected.value || props.disabled) return
  emit('complete', { event_id: props.step.event_id, participation_record_id: selected.value.record, session_date: selected.value.session })
}
</script>

<template>
  <article class="activity-card recommendation-card">
    <div class="activity-top">
      <span class="activity-icon"><AppIcon name="book" /></span>
      <span class="skill-tag">{{ t(`employee.${step.action}`) }}</span>
      <span class="activity-id">{{ step.event_id }}</span>
    </div>
    <h3>{{ step.title }}</h3>
    <p class="activity-meta"><AppIcon name="clock" />{{ t('employee.hours', { count: number(step.duration_hours) }) }} · {{ format(step.format) }}</p>
    <p v-if="step.next_session" class="session-date">{{ t('employee.nextSession', { date: date(step.next_session) }) }}</p>

    <h4>{{ t('employee.factors') }}</h4>
    <ul class="factor-list">
      <li v-for="(factor, index) in step.factors" :key="`${factor.code}-${index}`">
        <strong>{{ te(`employee.factor.${factor.code}`) ? t(`employee.factor.${factor.code}`) : factor.code }}</strong>
        <p>{{ factor.text }}</p>
      </li>
    </ul>

    <div class="step-forecast">
      <p>{{ t('employee.forecast') }}</p>
      <strong>{{ number(step.progress_before_pct) }}% <span aria-hidden="true">→</span> {{ number(step.progress_after_pct) }}%</strong>
      <span>{{ t('employee.coverage') }}</span>
    </div>
    <h4>{{ t('employee.skillChanges') }}</h4>
    <ul class="delta-list">
      <li v-for="delta in step.skill_deltas" :key="delta.skill_id">
        <span>{{ skillNames.get(delta.skill_id) || delta.skill_id }}</span>
        <strong>{{ delta.before }} → {{ delta.after }} <span class="delta-gain">(+{{ delta.delta }})</span></strong>
      </li>
    </ul>

    <form class="completion-form" @submit.prevent="complete">
      <label v-if="options.length > 1" :for="`participation-${step.event_id}`">{{ t('employee.participation') }}</label>
      <select v-if="options.length > 1" :id="`participation-${step.event_id}`" v-model="selection" :disabled="disabled" required>
        <option value="" disabled>{{ t('employee.selectParticipation') }}</option>
        <option v-for="option in options" :key="option.key" :value="option.key">{{ option.label }}</option>
      </select>
      <p v-else-if="options.length === 1" class="participation-hint">{{ options[0].label }}</p>
      <p v-else class="notice">{{ t('employee.futureSession') }}</p>
      <button class="dark-button" type="submit" :disabled="disabled || !selected"><AppIcon name="check" />{{ t('employee.completion') }}</button>
      <p class="completion-note">{{ t('employee.completionNote') }}</p>
    </form>
  </article>
</template>

<style scoped>
.recommendation-card { height: 100%; }
.recommendation-card .activity-top { flex-wrap: wrap; gap: 10px; }
.recommendation-card .activity-id { margin-left: auto; font-size: 14px; }
.recommendation-card .activity-meta { flex-wrap: wrap; font-size: 15px; }
.recommendation-card .skill-tag { font-size: 14px; }
h4 { margin: 22px 0 12px; font-size: 16px; }
.session-date, .participation-hint { color: var(--muted); font-size: 15px; line-height: 1.6; margin-top: 10px; }
.factor-list, .delta-list { list-style: none; padding: 0; margin: 0; }
.factor-list { display: grid; gap: 17px; }
.factor-list li { padding-left: 13px; border-left: 3px solid #e1efe7; font-size: 15px; line-height: 1.65; }
.factor-list strong { color: var(--green-dark); font-size: 14px; }
.factor-list p { margin: 4px 0 0; overflow-wrap: anywhere; }
.step-forecast { background: var(--green-light); border-radius: 12px; padding: 17px; margin-top: 24px; display: grid; gap: 8px; }
.step-forecast p, .step-forecast > span { font-size: 14px; color: var(--muted); }
.step-forecast strong { font-size: 25px; color: var(--green-dark); }
.step-forecast strong span { margin: 0 7px; font-weight: 400; }
.delta-list { margin-bottom: 20px; }
.delta-list li { display: flex; flex-wrap: wrap; gap: 4px 12px; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid var(--line); font-size: 15px; }
.delta-list strong { white-space: nowrap; }
.delta-gain { color: var(--green-dark); }
.completion-form { margin-top: auto; padding-top: 15px; }
.completion-form label { display: block; font-size: 15px; margin-bottom: 8px; }
.completion-form select { width: 100%; padding: 12px; min-height: 46px; background: white; border: 1px solid var(--line); border-radius: 10px; color: var(--ink); }
.completion-note { margin-top: 12px; color: var(--muted); font-size: 14px; line-height: 1.65; }
.completion-form .notice { margin-top: 0; }
</style>
