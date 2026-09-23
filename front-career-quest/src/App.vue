<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { supportedLocales as languages } from './i18n'
import { employees, events } from './data/career'
import CareerWorkspace from './components/CareerWorkspace.vue'

const { t, locale: language } = useI18n()
const navItems = [{ key: 'overview', icon: '⌂' }, { key: 'path', icon: '↗' }, { key: 'catalog', icon: '▦' }, { key: 'team', icon: '♧' }]
const pages = [...navItems.map(item => item.key), 'help', 'settings']
function readPage() { const value = location.hash.slice(1); return pages.includes(value) ? value : 'overview' }
const activeNav = ref(readPage())
function updatePage() { activeNav.value = readPage() }
onMounted(() => window.addEventListener('hashchange', updatePage))
onUnmounted(() => window.removeEventListener('hashchange', updatePage))
let savedProfile
try { savedProfile = localStorage.getItem('careerquest-profile') } catch { /* Storage is optional. */ }
const selectedId = ref(employees.some(person => person.employee_id === savedProfile) ? savedProfile : 'E0017')
const employee = computed(() => employees.find(person => person.employee_id === selectedId.value))
const initials = computed(() => employee.value.full_name.split(' ').map(part => part[0]).slice(0, 2).join(''))
watch(selectedId, value => { try { localStorage.setItem('careerquest-profile', value) } catch { /* Storage is optional. */ } })
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#overview"><span class="brand-mark">C</span><span>career<span class="brand-accent">quest</span></span></a>
      <div class="profile-mini"><div class="avatar avatar-small">{{ initials }}</div><div><strong>{{ employee.full_name }}</strong><span>{{ employee.grade }} · {{ employee.role }}</span></div></div>
      <nav :aria-label="t('pages.navigation')"><a v-for="item in navItems" :key="item.key" :href="`#${item.key}`" :class="['nav-item', { active: activeNav === item.key }]" :aria-current="activeNav === item.key ? 'page' : undefined"><span class="nav-icon">{{ item.icon }}</span>{{ t(item.key) }}<span v-if="item.key === 'catalog'" class="nav-count">{{ events.length }}</span></a></nav>
      <div class="sidebar-bottom"><a v-for="item in ['help', 'settings']" :key="item" :href="`#${item}`" :class="['nav-item', { active: activeNav === item }]" :aria-current="activeNav === item ? 'page' : undefined"><span class="nav-icon">{{ item === 'help' ? '?' : '⚙' }}</span>{{ t(item) }}</a><div class="sidebar-foot"><span>Career Quest · 2026</span><span>{{ language.toUpperCase() }}</span></div></div>
    </aside>
    <main class="content">
      <header class="topbar"><a class="mobile-brand" href="#overview"><span class="brand-mark">C</span> careerquest</a><div class="breadcrumbs"><a href="#overview">{{ t('home') }}</a> <span>/</span> {{ t(activeNav) }}</div><div class="top-actions"><div class="language-switcher" role="group" :aria-label="t('language')"><button v-for="option in languages" :key="option" :class="{ selected: language === option }" :aria-pressed="language === option" @click="language = option">{{ option.toUpperCase() }}</button></div><a href="#settings" class="avatar avatar-top" :aria-label="t('settings')">{{ initials }}</a></div></header>
      <nav class="mobile-nav" :aria-label="t('pages.navigation')"><a v-for="item in pages" :key="item" :href="`#${item}`" :class="{ active: activeNav === item }" :aria-current="activeNav === item ? 'page' : undefined">{{ t(item) }}</a></nav>
      <CareerWorkspace :page="activeNav" :employee="employee" @select-profile="selectedId = $event" />
    </main>
  </div>
</template>
