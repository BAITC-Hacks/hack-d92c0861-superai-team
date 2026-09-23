<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { supportedLocales as languages } from './i18n'

const { t, locale: language } = useI18n()
const activeNav = ref('overview')
const selectedFilter = ref('all')
const expandedSkills = ref(false)
const enrolled = ref([])
const navItems = [
  { key: 'overview', icon: '⌂' }, { key: 'path', icon: '↗' },
  { key: 'catalog', icon: '▦' }, { key: 'team', icon: '♧' },
]
const skills = [
  { key: 'systemDesign', category: 'hardSkill', current: 3, target: 4, color: 'teal' },
  { key: 'technicalLeadership', category: 'softSkill', current: 2, target: 4, color: 'coral' },
  { key: 'cloudArchitecture', category: 'hardSkill', current: 3, target: 4, color: 'blue' },
  { key: 'communication', category: 'softSkill', current: 4, target: 4, color: 'yellow' },
]
const activities = [
  { id: 'EV_018', type: 'course', title: 'reliableSystems', meta: 'courseMeta', skills: 'systemDesign', color: 'teal' },
  { id: 'EV_027', type: 'mentoring', title: 'leadershipPractice', meta: 'mentoringMeta', skills: 'technicalLeadership', color: 'coral' },
  { id: 'EV_031', type: 'workshop', title: 'cloudNative', meta: 'workshopMeta', skills: 'cloudArchitecture', color: 'blue' },
]
const filterOptions = ['all', 'course', 'mentoring', 'workshop']
const filteredActivities = computed(() => selectedFilter.value === 'all' ? activities : activities.filter((activity) => activity.type === selectedFilter.value))
function enroll(activity) { if (!enrolled.value.includes(activity.id)) enrolled.value.push(activity.id) }
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">C</span><span>career<span class="brand-accent">quest</span></span></div>
      <div class="profile-mini"><div class="avatar avatar-small">АС</div><div><strong>Анна Смирнова</strong><span>Senior · Product</span></div><span class="more">•••</span></div>
      <nav><button v-for="item in navItems" :key="item.key" :class="['nav-item', { active: activeNav === item.key }]" @click="activeNav = item.key"><span class="nav-icon">{{ item.icon }}</span>{{ t(item.key) }}<span v-if="item.key === 'catalog'" class="nav-count">12</span></button></nav>
      <div class="sidebar-bottom"><button class="nav-item"><span class="nav-icon">?</span>{{ t('help') }}</button><button class="nav-item"><span class="nav-icon">⚙</span>{{ t('settings') }}</button><div class="sidebar-foot"><span>Career Quest · 2026</span><span>{{ language.toUpperCase() }}</span></div></div>
    </aside>
    <main class="content">
      <header class="topbar"><button class="mobile-brand"><span class="brand-mark">C</span> careerquest</button><div class="breadcrumbs">{{ t('home') }} <span>/</span> {{ t(activeNav) }}</div><div class="top-actions"><div class="language-switcher" role="group" :aria-label="t('language')"><button v-for="option in languages" :key="option" :class="{ selected: language === option }" @click="language = option">{{ option.toUpperCase() }}</button></div><button class="icon-button">⌕</button><button class="icon-button notification">♢<i></i></button><div class="avatar avatar-top">АС</div></div></header>
      <div class="page-wrap">
        <section class="hero-row"><div><p class="eyebrow">{{ t('reportDate') }}</p><h1>{{ t('greeting') }}</h1><p class="hero-subtitle">{{ t('routeSubtitle') }}</p></div><button class="outline-button">{{ t('downloadReport') }} <span>↓</span></button></section>
        <section class="stats-grid"><article class="stat-card"><div class="stat-label">{{ t('currentGrade') }} <span>↗</span></div><div class="stat-value">Senior</div><div class="stat-note">{{ t('productManager') }}</div></article><article class="stat-card accent-card"><div class="stat-label">{{ t('progressToGoal') }} <span>↗</span></div><div class="progress-ring"><strong>72<small>%</small></strong></div><div><div class="stat-value compact">{{ t('lead') }}</div><div class="stat-note">{{ t('progressNote') }}</div></div></article><article class="stat-card"><div class="stat-label">{{ t('strongSkill') }} <span>↗</span></div><div class="stat-value skill-stat">{{ t('communication') }} <span>↗</span></div><div class="stat-note">{{ t('communicationNote') }}</div></article><article class="stat-card"><div class="stat-label">{{ t('activities2026') }} <span>↗</span></div><div class="stat-value">7</div><div class="stat-note positive">{{ t('previousYear') }}</div></article></section>
        <section class="main-grid"><article class="panel skills-panel"><div class="panel-heading"><div><p class="section-kicker">{{ t('development') }}</p><h2>{{ t('skillsToGrade') }}</h2></div><button class="text-button" @click="expandedSkills = !expandedSkills">{{ expandedSkills ? t('collapse') : t('allSkills') }} <span>→</span></button></div><div class="skill-list"><div v-for="skill in (expandedSkills ? skills : skills.slice(0, 3))" :key="skill.key" class="skill-row"><div class="skill-info"><div><strong>{{ t(skill.key) }}</strong><span>{{ t(skill.category) }}</span></div><b>{{ skill.current }}<em>/ {{ skill.target }}</em></b></div><div class="bar"><span :class="skill.color" :style="{ width: `${skill.current / 5 * 100}%` }"></span><i :style="{ left: `${skill.target / 5 * 100}%` }"></i></div></div></div><div class="legend"><span><i class="legend-current"></i> {{ t('currentLevel') }}</span><span><i class="legend-target"></i> {{ t('targetLead') }}</span></div></article><article class="panel goal-panel"><div class="panel-heading"><div><p class="section-kicker">{{ t('careerGoal') }}</p><h2>Product Lead</h2></div><span class="goal-icon">↗</span></div><p class="goal-copy">{{ t('goalCopy') }}</p><div class="goal-line"><span>{{ t('progress') }}</span><strong>72%</strong></div><div class="goal-bar"><span></span></div><div class="goal-footer"><span>{{ t('start') }}<br><b>{{ t('jan') }}</b></span><span class="goal-arrow">→</span><span class="goal-end">{{ t('goal') }}<br><b>{{ t('dec') }}</b></span></div><button class="dark-button">{{ t('openPath') }} <span>→</span></button></article></section>
        <section class="panel recommendations"><div class="panel-heading recommendations-head"><div><p class="section-kicker">{{ t('nextStep') }}</p><h2>{{ t('recommendations') }}</h2><p class="muted">{{ t('recommendedCopy') }}</p></div><div class="filters"><button v-for="filter in filterOptions" :key="filter" :class="{ selected: selectedFilter === filter }" @click="selectedFilter = filter">{{ t(filter) }}</button></div></div><div class="activity-grid"><div v-for="activity in filteredActivities" :key="activity.id" class="activity-card"><div class="activity-top"><span :class="['activity-icon', activity.color]">✦</span><span class="activity-type">{{ t(activity.type) }}</span><span class="activity-id">{{ activity.id }}</span></div><h3>{{ t(activity.title) }}</h3><p class="activity-meta">{{ t(activity.meta) }}</p><div class="activity-bottom"><span class="skill-tag">{{ t(activity.skills) }}</span><button :class="['enroll-button', { enrolled: enrolled.includes(activity.id) }]" @click="enroll(activity)">{{ enrolled.includes(activity.id) ? t('enrolled') : t('details') }}</button></div></div></div></section>
      </div>
    </main>
  </div>
</template>
