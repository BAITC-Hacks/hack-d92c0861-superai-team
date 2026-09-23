<script setup>
import { computed, ref } from 'vue'

const activeNav = ref('Обзор')
const selectedFilter = ref('Все')
const expandedSkills = ref(false)
const enrolled = ref([])
const navItems = [
  { label: 'Обзор', icon: '⌂' }, { label: 'Мой путь', icon: '↗' },
  { label: 'Каталог активностей', icon: '▦' }, { label: 'Команда', icon: '♧' },
]
const skills = [
  { name: 'Системный дизайн', category: 'Hard skill', current: 3, target: 4, color: 'teal' },
  { name: 'Техническое лидерство', category: 'Soft skill', current: 2, target: 4, color: 'coral' },
  { name: 'Облачная архитектура', category: 'Hard skill', current: 3, target: 4, color: 'blue' },
  { name: 'Коммуникация', category: 'Soft skill', current: 4, target: 4, color: 'yellow' },
]
const activities = [
  { id: 'EV_018', type: 'КУРС', title: 'Архитектура отказоустойчивых систем', meta: '6 часов  ·  Онлайн', skills: 'Системный дизайн', color: 'teal' },
  { id: 'EV_027', type: 'МЕНТОРИНГ', title: 'Практика технического лидерства', meta: '4 встречи  ·  Офлайн', skills: 'Техническое лидерство', color: 'coral' },
  { id: 'EV_031', type: 'ВОРКШОП', title: 'Cloud-native: от идеи до production', meta: '3 часа  ·  Онлайн', skills: 'Облачная архитектура', color: 'blue' },
]
const filteredActivities = computed(() => selectedFilter.value === 'Все' ? activities : activities.filter((activity) => activity.type === selectedFilter.value))
function enroll(activity) { if (!enrolled.value.includes(activity.id)) enrolled.value.push(activity.id) }
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="brand-mark">C</span><span>career<span class="brand-accent">quest</span></span></div>
      <div class="profile-mini"><div class="avatar avatar-small">АС</div><div><strong>Анна Смирнова</strong><span>Senior · Product</span></div><span class="more">•••</span></div>
      <nav><button v-for="item in navItems" :key="item.label" :class="['nav-item', { active: activeNav === item.label }]" @click="activeNav = item.label"><span class="nav-icon">{{ item.icon }}</span>{{ item.label }}<span v-if="item.label === 'Каталог активностей'" class="nav-count">12</span></button></nav>
      <div class="sidebar-bottom"><button class="nav-item"><span class="nav-icon">?</span>Помощь и поддержка</button><button class="nav-item"><span class="nav-icon">⚙</span>Настройки</button><div class="sidebar-foot"><span>Career Quest · 2026</span><span>RU</span></div></div>
    </aside>
    <main class="content">
      <header class="topbar"><button class="mobile-brand"><span class="brand-mark">C</span> careerquest</button><div class="breadcrumbs">Главная <span>/</span> {{ activeNav }}</div><div class="top-actions"><button class="icon-button">⌕</button><button class="icon-button notification">♢<i></i></button><div class="avatar avatar-top">АС</div></div></header>
      <div class="page-wrap">
        <section class="hero-row"><div><p class="eyebrow">СРЕЗ ДАННЫХ · 01 ОКТЯБРЯ 2026</p><h1>Добрый день, Анна</h1><p class="hero-subtitle">Вот как выглядит твой карьерный маршрут сейчас.</p></div><button class="outline-button">Скачать мой отчёт <span>↓</span></button></section>
        <section class="stats-grid"><article class="stat-card"><div class="stat-label">ТЕКУЩИЙ ГРЕЙД <span>↗</span></div><div class="stat-value">Senior</div><div class="stat-note">Product Manager</div></article><article class="stat-card accent-card"><div class="stat-label">ПРОГРЕСС ДО ЦЕЛИ <span>↗</span></div><div class="progress-ring"><strong>72<small>%</small></strong></div><div><div class="stat-value compact">Lead</div><div class="stat-note">ориентировочно через 8–12 мес.</div></div></article><article class="stat-card"><div class="stat-label">СИЛЬНЫЙ НАВЫК <span>↗</span></div><div class="stat-value skill-stat">Коммуникация <span>↗</span></div><div class="stat-note">4 / 5 · выше цели грейда</div></article><article class="stat-card"><div class="stat-label">АКТИВНОСТЕЙ В 2026 <span>↗</span></div><div class="stat-value">7</div><div class="stat-note positive">↑ 2 к прошлому году</div></article></section>
        <section class="main-grid"><article class="panel skills-panel"><div class="panel-heading"><div><p class="section-kicker">РАЗВИТИЕ</p><h2>Навыки до следующего грейда</h2></div><button class="text-button" @click="expandedSkills = !expandedSkills">{{ expandedSkills ? 'Свернуть' : 'Все навыки' }} <span>→</span></button></div><div class="skill-list"><div v-for="skill in (expandedSkills ? skills : skills.slice(0, 3))" :key="skill.name" class="skill-row"><div class="skill-info"><div><strong>{{ skill.name }}</strong><span>{{ skill.category }}</span></div><b>{{ skill.current }}<em>/ {{ skill.target }}</em></b></div><div class="bar"><span :class="skill.color" :style="{ width: `${skill.current / 5 * 100}%` }"></span><i :style="{ left: `${skill.target / 5 * 100}%` }"></i></div></div></div><div class="legend"><span><i class="legend-current"></i> Текущий уровень</span><span><i class="legend-target"></i> Цель Lead</span></div></article><article class="panel goal-panel"><div class="panel-heading"><div><p class="section-kicker">КАРЬЕРНАЯ ЦЕЛЬ</p><h2>Product Lead</h2></div><span class="goal-icon">↗</span></div><p class="goal-copy">Ты уже закрываешь 72% требований для следующего шага.</p><div class="goal-line"><span>Прогресс</span><strong>72%</strong></div><div class="goal-bar"><span></span></div><div class="goal-footer"><span>Начало пути<br><b>Jan 2026</b></span><span class="goal-arrow">→</span><span class="goal-end">Цель<br><b>Dec 2026</b></span></div><button class="dark-button">Открыть карьерный путь <span>→</span></button></article></section>
        <section class="panel recommendations"><div class="panel-heading recommendations-head"><div><p class="section-kicker">СЛЕДУЮЩИЙ ШАГ</p><h2>Рекомендованные активности</h2><p class="muted">Подобраны на основе твоих целей и текущего профиля навыков.</p></div><div class="filters"><button v-for="filter in ['Все', 'КУРС', 'МЕНТОРИНГ', 'ВОРКШОП']" :key="filter" :class="{ selected: selectedFilter === filter }" @click="selectedFilter = filter">{{ filter }}</button></div></div><div class="activity-grid"><div v-for="activity in filteredActivities" :key="activity.id" class="activity-card"><div class="activity-top"><span :class="['activity-icon', activity.color]">✦</span><span class="activity-type">{{ activity.type }}</span><span class="activity-id">{{ activity.id }}</span></div><h3>{{ activity.title }}</h3><p class="activity-meta">{{ activity.meta }}</p><div class="activity-bottom"><span class="skill-tag">{{ activity.skills }}</span><button :class="['enroll-button', { enrolled: enrolled.includes(activity.id) }]" @click="enroll(activity)">{{ enrolled.includes(activity.id) ? 'Записано ✓' : 'Подробнее →' }}</button></div></div></div></section>
      </div>
    </main>
  </div>
</template>
