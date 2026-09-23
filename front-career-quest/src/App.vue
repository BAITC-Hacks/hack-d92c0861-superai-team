<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { supportedLocales as languages } from './i18n'
import { employees, events } from './data/career'
import CareerWorkspace from './components/CareerWorkspace.vue'
import AppIcon from './components/AppIcon.vue'
import ProfilePage from './components/ProfilePage.vue'

const { t, locale: language } = useI18n()
const navItems = ['overview', 'path', 'catalog', 'team']
const utilityItems = ['help', 'settings']
const pages = [...navItems, ...utilityItems, 'profile']
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
function pageTitle(page) { return t(page === 'profile' ? 'design.profile' : page) }
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <a class="brand" href="#overview">
        <span class="brand-mark"><AppIcon name="growth" /></span>
        <span class="brand-copy"><span>Career <span class="brand-accent">Quest</span></span><span class="brand-subtitle">{{ t('design.platform') }}</span></span>
      </a>
      <p class="sidebar-label">{{ t('design.workspace') }}</p>
      <nav :aria-label="t('pages.navigation')">
        <a v-for="item in navItems" :key="item" :href="`#${item}`" :class="['nav-item', { active: activeNav === item }]" :aria-current="activeNav === item ? 'page' : undefined">
          <AppIcon :name="item" class="nav-icon" />
          <span>{{ t(item) }}</span>
          <span v-if="item === 'catalog'" class="nav-count">{{ events.length }}</span>
        </a>
      </nav>
      <div class="sidebar-bottom">
        <a v-for="item in utilityItems" :key="item" :href="`#${item}`" :class="['nav-item', { active: activeNav === item }]" :aria-current="activeNav === item ? 'page' : undefined"><AppIcon :name="item" class="nav-icon" /><span>{{ t(item) }}</span></a>
        <div class="sidebar-foot"><span>Career Quest · 2026</span><span>{{ language.toUpperCase() }}</span></div>
      </div>
    </aside>
    <main class="content">
      <header class="topbar">
        <a class="mobile-brand" href="#overview"><span class="brand-mark"><AppIcon name="growth" /></span><span>Career Quest</span></a>
        <div class="breadcrumbs"><a href="#overview">{{ t('home') }}</a><AppIcon name="chevron" /><span>{{ pageTitle(activeNav) }}</span></div>
        <div class="top-actions">
          <div class="language-switcher" role="group" :aria-label="t('language')"><button v-for="option in languages" :key="option" :class="{ selected: language === option }" :aria-pressed="language === option" @click="language = option">{{ option.toUpperCase() }}</button></div>
          <a href="#settings" class="top-settings" :aria-label="t('settings')" :aria-current="activeNav === 'settings' ? 'page' : undefined"><AppIcon name="settings" /></a>
          <a href="#profile" class="profile-trigger" :aria-label="`${t('design.profile')}: ${employee.full_name}`" :aria-current="activeNav === 'profile' ? 'page' : undefined">
            <span class="avatar avatar-top">{{ initials }}</span>
            <span class="profile-trigger-copy"><strong>{{ employee.full_name }}</strong><span>{{ t('design.profile') }}</span></span>
            <AppIcon name="chevron" />
          </a>
        </div>
      </header>
      <nav class="mobile-nav" :aria-label="t('pages.navigation')"><a v-for="item in [...navItems, ...utilityItems]" :key="item" :href="`#${item}`" :class="{ active: activeNav === item }" :aria-current="activeNav === item ? 'page' : undefined"><AppIcon :name="item" />{{ t(item) }}</a></nav>
      <ProfilePage v-if="activeNav === 'profile'" :employee="employee" />
      <CareerWorkspace v-else :page="activeNav" :employee="employee" @select-profile="selectedId = $event" />
    </main>
  </div>
</template>
