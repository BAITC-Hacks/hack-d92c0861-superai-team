<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { employees, skills } from '../data/career'
import { translateDatasetField } from '../i18n'
import AppIcon from './AppIcon.vue'

const props = defineProps({ employee: { type: Object, required: true } })
const { t, locale } = useI18n()
const initials = computed(() => props.employee.full_name.split(' ').map(part => part[0]).slice(0, 2).join(''))
const manager = computed(() => employees.find(person => person.employee_id === props.employee.manager_id))
const profileSkills = computed(() => Object.entries(props.employee.skills).sort((a, b) => b[1] - a[1]).map(([id, level]) => {
  const skill = skills.find(item => item.skill_id === id)
  return { id, level, type: skill?.type || 'hard', name: translateDatasetField('skills', id, 'name', skill?.name || id) }
}))
function date(value) { return new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${value}T00:00:00Z`)) }
</script>

<template>
  <div class="page-wrap profile-page">
    <section class="hero-row">
      <div><p class="eyebrow">{{ t('design.personalSpace') }}</p><h1>{{ t('design.profile') }}</h1><p class="hero-subtitle">{{ t('design.profileIntro') }}</p></div>
      <a href="#path" class="outline-button page-link">{{ t('openPath') }}<AppIcon name="arrow" /></a>
    </section>

    <section class="panel profile-hero">
      <div class="avatar profile-avatar">{{ initials }}</div>
      <div class="profile-details"><p class="section-kicker">{{ employee.employee_id }}</p><h2>{{ employee.full_name }}</h2><p>{{ employee.role }} · {{ employee.grade }}</p><span class="skill-tag">{{ employee.department }}</span></div>
      <div class="profile-status"><AppIcon name="user" /><span>{{ t('design.personalAccount') }}</span></div>
    </section>

    <div class="main-grid profile-grid">
      <section class="panel">
        <div class="panel-heading"><h2>{{ t('design.aboutProfile') }}</h2><AppIcon name="briefcase" /></div>
        <dl class="profile-facts">
          <div class="profile-fact"><dt>{{ t('pages.role') }}</dt><dd>{{ employee.role }}</dd></div>
          <div class="profile-fact"><dt>{{ t('design.grade') }}</dt><dd>{{ employee.grade }}</dd></div>
          <div class="profile-fact"><dt>{{ t('pages.department') }}</dt><dd>{{ employee.department }}</dd></div>
          <div class="profile-fact"><dt>{{ t('pages.manager') }}</dt><dd>{{ manager?.full_name || t('pages.noManager') }}</dd></div>
          <div class="profile-fact"><dt>{{ t('design.joined') }}</dt><dd>{{ date(employee.hire_date) }}</dd></div>
          <div class="profile-fact"><dt>{{ t('design.lastReview') }}</dt><dd>{{ date(employee.last_review_date) }}</dd></div>
        </dl>
      </section>
      <section class="panel goal-panel profile-target">
        <p class="section-kicker">{{ t('careerGoal') }}</p>
        <AppIcon name="target" class="profile-target-icon" />
        <h2>{{ employee.career_goal ? `${employee.career_goal.target_role} · ${employee.career_goal.target_grade}` : t('pages.noGoal') }}</h2>
        <p class="goal-copy">{{ t(employee.career_goal ? 'design.profileGoalCopy' : 'pages.noGoalExplore') }}</p>
        <a href="#path" class="dark-button page-link">{{ t('openPath') }}<AppIcon name="arrow" /></a>
      </section>
    </div>

    <section class="panel profile-skills">
      <div class="panel-heading"><div><p class="section-kicker">{{ t('design.expertise') }}</p><h2>{{ t('design.profileSkills') }}</h2></div><span class="skill-tag">{{ t('design.skillsCount', { count: profileSkills.length }) }}</span></div>
      <p class="muted">{{ t('pages.reviewDate', { date: date(employee.last_review_date) }) }}</p>
      <div class="profile-skill-list">
        <div v-for="skill in profileSkills" :key="skill.id" class="profile-skill-row">
          <div class="skill-info"><div><strong>{{ skill.name }}</strong><span>{{ t(skill.type === 'hard' ? 'hardSkill' : 'softSkill') }}</span></div><b>{{ skill.level }}<em> / 5</em></b></div>
          <div class="bar"><span class="teal" :style="{ width: `${skill.level / 5 * 100}%` }"></span></div>
        </div>
      </div>
    </section>
  </div>
</template>
