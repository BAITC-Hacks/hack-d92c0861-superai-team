<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { translateDatasetField, supportedLocales } from '../i18n'
import { employees, events, profiles, skills, history, snapshotDate, requirementsFor, progressFor, eligibleFor, completedBy, recommendFor } from '../data/career'
import EventCard from './EventCard.vue'
import AppIcon from './AppIcon.vue'
const props = defineProps({ page: { type: String, required: true }, employee: { type: Object, required: true } })
const emit = defineEmits(['select-profile'])
const { t, locale } = useI18n()
const roles = [...new Set(profiles.map(profile => profile.role))]
const grades = ['Junior', 'Middle', 'Senior', 'Lead']
const targetRole = ref(''), targetGrade = ref('')
const query = ref(''), type = ref('all'), format = ref('all'), suitableOnly = ref(false)
const teamQuery = ref(''), department = ref('all'), grade = ref('all')
const expanded = ref(false), selectedEvent = ref(null), selectedPerson = ref(null)
const eventDialog = ref(null), personDialog = ref(null)
const plans = ref({}), storageError = ref(false)
try {
  const saved = JSON.parse(localStorage.getItem('careerquest-plans') || '{}')
  if (saved && typeof saved === 'object' && !Array.isArray(saved)) {
    plans.value = Object.fromEntries(Object.entries(saved).filter(([id, ids]) => employees.some(person => person.employee_id === id) && Array.isArray(ids)).map(([id, ids]) => [id, ids.filter(eventId => events.some(event => event.event_id === eventId))]))
  }
} catch { /* Start with an empty plan when saved data is unavailable. */ }
watch(() => props.employee, person => {
  targetRole.value = person.career_goal?.target_role || person.role
  targetGrade.value = person.career_goal?.target_grade || person.grade
}, { immediate: true })
watch(() => props.page, page => {
  eventDialog.value?.close()
  personDialog.value?.close()
  if (page === 'overview') {
    targetRole.value = props.employee.career_goal?.target_role || props.employee.role
    targetGrade.value = props.employee.career_goal?.target_grade || props.employee.grade
  }
})
const requirements = computed(() => requirementsFor(props.employee, targetRole.value, targetGrade.value))
const progress = computed(() => progressFor(requirements.value))
const gaps = computed(() => requirements.value.filter(skill => skill.current < skill.target))
const recommendations = computed(() => recommendFor(props.employee, requirements.value))
const personalHistory = computed(() => history.filter(row => row.employee_id === props.employee.employee_id).sort((a, b) => b.date.localeCompare(a.date)))
const planIds = computed(() => plans.value[props.employee.employee_id] || [])
const plannedEvents = computed(() => events.filter(event => planIds.value.includes(event.event_id)))
const strongest = computed(() => Object.entries(props.employee.skills).sort((a, b) => b[1] - a[1])[0])
const eventTypes = [...new Set(events.map(event => event.type))]
const departments = [...new Set(employees.map(person => person.department))]
const catalog = computed(() => events.filter(event => {
  const text = `${event.event_id} ${event.title} ${event.description} ${eventName(event)} ${event.develops_skills.map(item => skillName(item.skill_id)).join(' ')}`.toLocaleLowerCase(locale.value)
  return text.includes(query.value.trim().toLocaleLowerCase(locale.value)) && (type.value === 'all' || event.type === type.value) && (format.value === 'all' || event.format === format.value) && (!suitableOnly.value || eligibleFor(event, props.employee))
}))
const team = computed(() => employees.filter(person => `${person.full_name} ${person.role} ${person.employee_id}`.toLocaleLowerCase(locale.value).includes(teamQuery.value.trim().toLocaleLowerCase(locale.value)) && (department.value === 'all' || person.department === department.value) && (grade.value === 'all' || person.grade === grade.value)))
const manager = computed(() => employees.find(person => person.employee_id === props.employee.manager_id))
function skillName(id) { const skill = skills.find(item => item.skill_id === id); return translateDatasetField('skills', id, 'name', skill?.name || id) }
function eventName(event) { return translateDatasetField('events', event.event_id, 'title', event.title) }
function date(value) { return new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`)) }
function togglePlan(event) {
  const ids = planIds.value
  plans.value = { ...plans.value, [props.employee.employee_id]: ids.includes(event.event_id) ? ids.filter(id => id !== event.event_id) : [...ids, event.event_id] }
  try { localStorage.setItem('careerquest-plans', JSON.stringify(plans.value)); storageError.value = false } catch { storageError.value = true }
}
async function showEvent(event) { selectedEvent.value = event; await nextTick(); eventDialog.value.showModal() }
async function showPerson(person) { selectedPerson.value = person; await nextTick(); personDialog.value.showModal() }
function resetCatalog() { query.value = ''; type.value = 'all'; format.value = 'all'; suitableOnly.value = false }
function canPlan(event) { return !event.mandatory && eligibleFor(event, props.employee) && (event.event_id === 'EV_036' || !completedBy(event, props.employee)) }
function downloadReport() {
  const report = { as_of_date: snapshotDate, employee: props.employee, comparison: { role: targetRole.value, grade: targetGrade.value, progress_pct: progress.value, requirements: requirements.value }, planned_event_ids: planIds.value, history: personalHistory.value }
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }))
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = `career-quest-${props.employee.employee_id}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>

<template>
  <div :class="['page-wrap', `page-${page}`]">
    <section :class="['hero-row', { 'hero-overview': page === 'overview' }]">
      <div class="hero-copy">
        <p class="eyebrow"><span class="status-dot" aria-hidden="true"></span>{{ t('pages.snapshot', { date: date(snapshotDate) }) }}</p>
        <h1>{{ page === 'overview' ? t('pages.hello', { name: employee.full_name.split(' ')[0] }) : t(page) }}</h1>
        <p class="hero-subtitle">{{ t(`pages.intro.${page}`) }}</p>
        <a v-if="page === 'overview'" class="hero-action" href="#path">{{ t('openPath') }}<AppIcon name="arrow" /></a>
      </div>
      <div v-if="page === 'overview'" class="hero-art" aria-hidden="true">
        <div class="orbit orbit-one"></div><div class="orbit orbit-two"></div>
        <div class="growth-step step-one"></div><div class="growth-step step-two"></div><div class="growth-step step-three"><AppIcon name="path" /></div>
        <div class="growth-coin"><AppIcon name="award" /></div>
        <div class="hero-target"><span>{{ t('nextStep') }}</span><strong>{{ employee.career_goal?.target_grade || t('pages.targetRole') }}</strong><AppIcon name="arrow" /></div>
      </div>
      <button v-else-if="page === 'path'" class="outline-button" @click="downloadReport"><AppIcon name="download" />{{ t('downloadReport') }}</button>
    </section>
    <p v-if="storageError" class="notice" role="status">{{ t('pages.storageError') }}</p>

    <template v-if="page === 'overview'">
      <div class="section-toolbar"><h2>{{ t('design.yourOverview') }}</h2><button class="text-button" @click="downloadReport"><AppIcon name="download" />{{ t('downloadReport') }}</button></div>
      <section class="stats-grid">
        <article class="stat-card"><div class="stat-top"><span class="stat-icon"><AppIcon name="briefcase" /></span><div class="stat-label">{{ t('currentGrade') }}</div></div><div class="stat-value">{{ employee.grade }}</div><div class="stat-note">{{ employee.role }}</div></article>
        <article class="stat-card"><div class="stat-top"><span class="stat-icon"><AppIcon name="path" /></span><div class="stat-label">{{ t('progressToGoal') }}</div></div><div class="stat-value">{{ employee.career_goal ? `${progress}%` : '—' }}</div><div class="stat-note">{{ employee.career_goal ? `${targetRole} · ${targetGrade}` : t('pages.noGoal') }}</div></article>
        <article class="stat-card"><div class="stat-top"><span class="stat-icon gold"><AppIcon name="award" /></span><div class="stat-label">{{ t('strongSkill') }}</div></div><div class="stat-value skill-stat">{{ skillName(strongest[0]) }}</div><div class="stat-note">{{ strongest[1] }} / 5</div></article>
        <article class="stat-card"><div class="stat-top"><span class="stat-icon"><AppIcon name="check" /></span><div class="stat-label">{{ t('pages.completed') }}</div></div><div class="stat-value">{{ personalHistory.filter(row => row.status === 'completed').length }}</div><div class="stat-note">{{ t('pages.historyPeriod') }}</div></article>
      </section>
      <section class="main-grid"><article class="panel"><p class="section-kicker">{{ t('development') }}</p><h2>{{ t('pages.prioritySkills') }}</h2><p class="muted">{{ t('pages.reviewDate', { date: date(employee.last_review_date) }) }}</p><div class="skill-list"><div v-for="skill in gaps.slice(0, 4)" :key="skill.skill_id"><div class="skill-info"><strong>{{ skillName(skill.skill_id) }}</strong><b>{{ skill.current }} / {{ skill.target }}</b></div><div class="bar"><span class="teal" :style="{ width: `${skill.current / 5 * 100}%` }"></span><i :style="{ left: `${skill.target / 5 * 100}%` }"></i></div></div><p v-if="!gaps.length" class="muted">{{ t('pages.noGaps') }}</p></div><a class="text-button page-link" href="#path">{{ t('openPath') }}<AppIcon name="arrow" /></a></article><article class="panel goal-panel">
          <div class="panel-heading"><p class="section-kicker">{{ t('careerGoal') }}</p><span class="goal-emblem"><AppIcon name="path" /></span></div>
          <h2>{{ employee.career_goal ? `${targetRole} · ${targetGrade}` : t('pages.noGoal') }}</h2>
          <div v-if="employee.career_goal" class="goal-progress"><strong>{{ progress }}<span>%</span></strong><span>{{ t('design.goalProgress') }}</span></div>
          <div v-if="employee.career_goal" class="goal-bar"><span :style="{ width: `${progress}%` }"></span></div>
          <p class="goal-plan-count"><AppIcon name="book" />{{ t('pages.plannedCount', { count: plannedEvents.length }) }}</p>
          <details class="goal-method"><summary>{{ t('design.howCalculated') }}</summary><p>{{ t('pages.progressExplanation') }}</p></details>
          <a class="dark-button page-link" href="#path">{{ t('openPath') }}<AppIcon name="arrow" /></a>
        </article></section>
      <section class="panel"><div class="panel-heading"><div><p class="section-kicker">{{ t('nextStep') }}</p><h2>{{ t('recommendations') }}</h2></div><a href="#catalog" class="text-button">{{ t('catalog') }}<AppIcon name="arrow" /></a></div><p class="muted">{{ t('pages.recommendationNote') }}</p><div class="activity-grid spaced"><EventCard v-for="event in recommendations.slice(0, 3)" :key="event.event_id" :event="event" :planned="planIds.includes(event.event_id)" @details="showEvent" /></div><p v-if="!recommendations.length" class="empty-state">{{ t('pages.noRecommendations') }}</p></section>
    </template>

    <template v-else-if="page === 'path'">
      <section class="panel"><div class="panel-heading"><div><p class="section-kicker">{{ t('careerGoal') }}</p><h2>{{ employee.role }} · {{ employee.grade }} → {{ targetRole }} · {{ targetGrade }}</h2></div><span class="progress-badge">{{ progress }}%</span></div><p v-if="!employee.career_goal" class="notice">{{ t('pages.noGoalExplore') }}</p><div class="toolbar"><label>{{ t('pages.targetRole') }}<select v-model="targetRole"><option v-for="role in roles" :key="role">{{ role }}</option></select></label><label>{{ t('pages.targetGrade') }}<select v-model="targetGrade"><option v-for="item in grades" :key="item">{{ item }}</option></select></label></div><p class="muted">{{ t('pages.comparisonOnly') }}</p><div class="grade-track"><div v-for="item in grades" :key="item" :class="{ current: item === employee.grade, target: item === targetGrade }"><strong>{{ item }}</strong><span>{{ item === employee.grade ? t('pages.current') : item === targetGrade ? t('goal') : '·' }}</span></div></div><p class="muted">{{ t('pages.progressExplanation') }} {{ t('pages.reviewDate', { date: date(employee.last_review_date) }) }}</p></section>
      <section class="panel spaced"><div class="panel-heading"><h2>{{ t('pages.requirements') }}</h2><span class="skill-tag">{{ t('pages.gapsCount', { count: gaps.length }) }}</span></div><div class="skill-list"><div v-for="skill in requirements" :key="skill.skill_id" class="skill-row"><div class="skill-info"><div><strong>{{ skillName(skill.skill_id) }}</strong><span>{{ t(skill.type === 'hard' ? 'hardSkill' : 'softSkill') }} · {{ t(skill.critical ? 'pages.critical' : 'pages.standard') }}</span></div><b :class="{ positive: skill.current >= skill.target }">{{ skill.current }}<em> / {{ skill.target }}</em></b></div><div class="bar"><span :class="skill.current >= skill.target ? 'teal' : 'coral'" :style="{ width: `${skill.current / 5 * 100}%` }"></span><i :style="{ left: `${skill.target / 5 * 100}%` }"></i></div></div></div></section>
      <section class="panel spaced"><h2>{{ t('pages.myPlan') }}</h2><p class="muted">{{ t('pages.localPlan') }}</p><div class="activity-grid spaced"><EventCard v-for="event in plannedEvents" :key="event.event_id" :event="event" planned @details="showEvent" /></div><div v-if="!plannedEvents.length" class="empty-state"><p>{{ t('pages.emptyPlan') }}</p><a href="#catalog" class="outline-button page-link">{{ t('catalog') }}<AppIcon name="arrow" /></a></div></section>
      <section class="panel spaced"><div class="panel-heading"><h2>{{ t('pages.history') }}</h2><button class="text-button" @click="expanded = !expanded">{{ t(expanded ? 'collapse' : 'pages.showAll') }}</button></div><div class="table-scroll"><table><thead><tr><th>{{ t('pages.date') }}</th><th>{{ t('pages.event') }}</th><th>{{ t('pages.status') }}</th><th>{{ t('progress') }}</th></tr></thead><tbody><tr v-for="row in personalHistory.slice(0, expanded ? undefined : 5)" :key="row.record_id"><td>{{ date(row.date) }}</td><td><button class="table-link" @click="showEvent(events.find(event => event.event_id === row.event_id))">{{ eventName(events.find(event => event.event_id === row.event_id)) }}</button></td><td>{{ t(`pages.statuses.${row.status}`) }}</td><td>{{ row.completion_pct }}%</td></tr></tbody></table></div><p v-if="!personalHistory.length" class="empty-state">{{ t('pages.noHistory') }}</p></section>
    </template>

    <template v-else-if="page === 'catalog'">
      <section class="panel"><div class="toolbar"><label class="search-field">{{ t('pages.search') }}<input v-model="query" type="search" :placeholder="t('pages.searchEvents')"></label><label>{{ t('pages.type') }}<select v-model="type"><option value="all">{{ t('all') }}</option><option v-for="item in eventTypes" :key="item" :value="item">{{ t(`pages.types.${item}`) }}</option></select></label><label>{{ t('pages.format') }}<select v-model="format"><option value="all">{{ t('all') }}</option><option v-for="item in ['online', 'offline', 'self_paced']" :key="item" :value="item">{{ t(`pages.formats.${item}`) }}</option></select></label></div><div class="filter-summary"><label class="checkbox-label"><input v-model="suitableOnly" type="checkbox">{{ t('pages.suitableOnly') }}</label><span role="status">{{ t('pages.results', { count: catalog.length }) }}</span><button class="text-button" @click="resetCatalog">{{ t('pages.reset') }}</button></div></section><div class="activity-grid catalog-grid spaced"><EventCard v-for="event in catalog" :key="event.event_id" :event="event" :planned="planIds.includes(event.event_id)" @details="showEvent" /></div><div v-if="!catalog.length" class="panel empty-state"><h2>{{ t('pages.noResults') }}</h2><p>{{ t('pages.changeFilters') }}</p><button class="outline-button" @click="resetCatalog">{{ t('pages.reset') }}</button></div>
    </template>

    <template v-else-if="page === 'team'">
      <section class="stats-grid team-stats"><article class="stat-card"><div class="stat-label">{{ t('pages.people') }}</div><div class="stat-value">{{ employees.length }}</div></article><article class="stat-card"><div class="stat-label">{{ t('pages.departments') }}</div><div class="stat-value">{{ departments.length }}</div></article><article class="stat-card"><div class="stat-label">{{ t('pages.manager') }}</div><div class="stat-value skill-stat">{{ manager?.full_name || t('pages.noManager') }}</div></article></section><section class="panel"><div class="toolbar"><label class="search-field">{{ t('pages.search') }}<input v-model="teamQuery" type="search" :placeholder="t('pages.searchPeople')"></label><label>{{ t('pages.department') }}<select v-model="department"><option value="all">{{ t('all') }}</option><option v-for="item in departments" :key="item">{{ item }}</option></select></label><label>{{ t('currentGrade') }}<select v-model="grade"><option value="all">{{ t('all') }}</option><option v-for="item in grades" :key="item">{{ item }}</option></select></label></div><p class="muted" role="status">{{ t('pages.results', { count: team.length }) }}</p><div class="table-scroll"><table><thead><tr><th>{{ t('pages.person') }}</th><th>{{ t('pages.department') }}</th><th>{{ t('pages.role') }}</th><th>{{ t('currentGrade') }}</th></tr></thead><tbody><tr v-for="person in team" :key="person.employee_id"><td><button class="table-link" @click="showPerson(person)">{{ person.full_name }}</button><small>{{ person.employee_id }}</small></td><td>{{ person.department }}</td><td>{{ person.role }}</td><td><span class="skill-tag">{{ person.grade }}</span></td></tr></tbody></table></div><div v-if="!team.length" class="empty-state"><p>{{ t('pages.noResults') }}</p><button class="outline-button" @click="teamQuery = ''; department = 'all'; grade = 'all'">{{ t('pages.reset') }}</button></div></section>
    </template>

    <template v-else-if="page === 'settings'">
      <section class="panel settings-panel"><h2>{{ t('pages.preferences') }}</h2><label>{{ t('language') }}<select v-model="locale"><option v-for="item in supportedLocales" :key="item" :value="item">{{ { ru: 'Русский', kk: 'Қазақша', en: 'English' }[item] }}</option></select></label><label>{{ t('pages.demoProfile') }}<select :value="employee.employee_id" @change="emit('select-profile', $event.target.value)"><option v-for="person in employees" :key="person.employee_id" :value="person.employee_id">{{ person.full_name }} · {{ person.role }} · {{ person.grade }}</option></select></label><p class="notice">{{ t('pages.syntheticData') }}</p><p class="muted">{{ t('pages.autoSave') }}</p></section><section class="panel spaced"><h2>{{ t('pages.dataSource') }}</h2><p class="body-copy">{{ t('pages.sourceDescription') }}</p><p class="muted">{{ t('pages.localPlan') }}</p></section>
    </template>

    <template v-else-if="page === 'help'">
      <section class="panel"><p class="section-kicker">CAREER QUEST</p><h2>{{ t('pages.faq') }}</h2><details v-for="item in ['progress', 'recommendations', 'plan', 'language', 'data']" :key="item" class="faq-item"><summary>{{ t(`pages.faqItems.${item}.question`) }}</summary><p>{{ t(`pages.faqItems.${item}.answer`) }}</p></details></section><section class="panel goal-panel spaced"><h2>{{ t('pages.startHere') }}</h2><p class="body-copy">{{ t('pages.startCopy') }}</p><a class="outline-button page-link" href="#path">{{ t('openPath') }}<AppIcon name="arrow" /></a></section>
    </template>

    <dialog ref="eventDialog" class="detail-dialog" aria-labelledby="event-dialog-title" @click="event => { if (event.target === eventDialog) eventDialog.close() }">
      <template v-if="selectedEvent"><div class="panel-heading"><span class="section-kicker">{{ selectedEvent.event_id }} · {{ t(`pages.types.${selectedEvent.type}`) }}</span><button class="outline-button" :aria-label="t('pages.close')" @click="eventDialog.close()">×</button></div><h2 id="event-dialog-title">{{ eventName(selectedEvent) }}</h2><p class="body-copy">{{ translateDatasetField('events', selectedEvent.event_id, 'description', selectedEvent.description) }}</p><p class="notice">{{ t('pages.hours', { count: selectedEvent.duration_hours }) }} · {{ t(`pages.formats.${selectedEvent.format}`) }}</p><h3>{{ t('pages.develops') }}</h3><ul><li v-for="skill in selectedEvent.develops_skills" :key="skill.skill_id">{{ skillName(skill.skill_id) }} · {{ t('pages.skillGain', { gain: skill.gain, max: skill.max_level }) }}</li></ul><p v-if="!selectedEvent.develops_skills.length" class="muted">{{ t('pages.noSkillGain') }}</p><h3>{{ t('pages.prerequisites') }}</h3><ul><li v-for="(level, id) in selectedEvent.prerequisites" :key="id">{{ skillName(id) }} ≥ {{ level }}</li></ul><p v-if="!Object.keys(selectedEvent.prerequisites).length" class="muted">{{ t('pages.none') }}</p><p class="body-copy">{{ t('pages.audience') }}: {{ selectedEvent.target_roles.join(', ') }} · {{ selectedEvent.target_grades.join(', ') }}</p><h3>{{ t('pages.sessions') }}</h3><p class="body-copy">{{ selectedEvent.format === 'self_paced' ? t('pages.anytime') : selectedEvent.upcoming_sessions.map(date).join(' · ') || t('pages.noSessions') }}</p><p v-if="!canPlan(selectedEvent)" class="notice">{{ t(selectedEvent.mandatory ? 'pages.hrAssigned' : completedBy(selectedEvent, employee) && selectedEvent.event_id !== 'EV_036' ? 'pages.alreadyCompleted' : 'pages.notEligible') }}</p><button class="dark-button" :disabled="!planIds.includes(selectedEvent.event_id) && !canPlan(selectedEvent)" @click="togglePlan(selectedEvent)">{{ t(planIds.includes(selectedEvent.event_id) ? 'pages.removePlan' : 'pages.addPlan') }}</button><p class="muted" role="status">{{ t(planIds.includes(selectedEvent.event_id) ? 'pages.inPlan' : 'pages.localPlan') }}</p></template>
    </dialog>
    <dialog ref="personDialog" class="detail-dialog" aria-labelledby="person-dialog-title" @click="event => { if (event.target === personDialog) personDialog.close() }">
      <template v-if="selectedPerson"><div class="panel-heading"><span class="section-kicker">{{ selectedPerson.employee_id }}</span><button class="outline-button" :aria-label="t('pages.close')" @click="personDialog.close()">×</button></div><h2 id="person-dialog-title">{{ selectedPerson.full_name }}</h2><p class="body-copy">{{ selectedPerson.role }} · {{ selectedPerson.grade }}<br>{{ selectedPerson.department }}</p><p class="notice">{{ t('careerGoal') }}: {{ selectedPerson.career_goal ? `${selectedPerson.career_goal.target_role} · ${selectedPerson.career_goal.target_grade}` : t('pages.noGoal') }}</p><h3>{{ t('pages.topSkills') }}</h3><div class="skill-list"><div v-for="[id, level] in Object.entries(selectedPerson.skills).sort((a,b) => b[1] - a[1]).slice(0, 5)" :key="id" class="skill-info"><strong>{{ skillName(id) }}</strong><span>{{ level }} / 5</span></div></div><p class="muted spaced">{{ t('pages.reviewDate', { date: date(selectedPerson.last_review_date) }) }}</p></template>
    </dialog>
  </div>
</template>
