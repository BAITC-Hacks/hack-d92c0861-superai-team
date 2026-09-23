<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { supportedLocales } from './i18n.js'
import { createCareerSession } from './session.js'
import AppIcon from './components/AppIcon.vue'
import EmployeeView from './components/EmployeeView.vue'
import HrView from './components/HrView.vue'
import CatalogView from './components/CatalogView.vue'
const { t, locale } = useI18n()
const session = createCareerSession()
const { state } = session
const tokenInput = ref('')
const route = ref(typeof location === 'undefined' ? 'overview' : location.hash.slice(1) || 'overview')
const page = computed(() => {
  if (route.value === 'hr' && state.identity?.role !== 'hr') return 'overview'
  return ['overview','profile','catalog','hr','settings','help'].includes(route.value) ? route.value : 'overview'
})
function updateRoute() { route.value = location.hash.slice(1) || 'overview' }
onMounted(() => window.addEventListener('hashchange', updateRoute))
onUnmounted(() => window.removeEventListener('hashchange', updateRoute))
watch([page, () => state.identity], ([value, identity]) => { if (identity?.role === 'hr' && value === 'hr' && !state.hr) session.loadHR() })
const employee = computed(() => state.profile?.employee)
const initials = computed(() => state.identity?.role === 'hr' ? 'HR' : employee.value?.full_name?.split(' ').map(part => part[0]).slice(0, 2).join('') || 'CQ')
const nav = computed(() => [{ key: 'overview', title: 'integration.overview', icon: 'path' }, { key: 'catalog', title: 'catalog', icon: 'catalog' }, ...(state.identity?.role === 'hr' ? [{ key: 'hr', title: 'integration.hr', icon: 'team' }] : [])])
const locked = computed(() => state.completion.busy || !!state.completion.pending || state.importing)
function title(value) { return t(value === 'profile' ? 'integration.profile' : value === 'overview' ? 'integration.overview' : value === 'hr' ? 'integration.hr' : value) }
function displayError(error) {
  if (!error) return null
  const status = [0,401,403,404,408,409,422,501].includes(error.status) ? error.status : 500
  return { ...error, message: `${t(`integration.errors.${status}`)}${error.message ? ` ${error.message}` : ''}` }
}
const completion = computed(() => ({ ...state.completion, error: displayError(state.completion.error) }))
async function login() { const token = tokenInput.value; tokenInput.value = ''; await session.login(token) }
function logout() { session.logout(); tokenInput.value = ''; location.hash = 'overview' }
async function selectEmployee(id) { await session.selectEmployee(id); location.hash = 'overview' }
</script>

<template>
  <div v-if="!state.identity" class="login-shell">
    <div class="login-brand brand"><span class="brand-mark"><AppIcon name="growth" /></span><span class="brand-copy">Career Quest<span class="brand-subtitle">{{ t('design.platform') }}</span></span></div>
    <section class="login-story"><p class="eyebrow">CAREER QUEST</p><h1>{{ t('integration.welcome') }}</h1><p>{{ t('integration.loginCopy') }}</p><AppIcon name="path" class="login-art" /></section>
    <form class="panel login-form" @submit.prevent="login"><h2>{{ t('integration.signIn') }}</h2><label for="access-token">{{ t('integration.token') }}<input id="access-token" v-model="tokenInput" type="password" autocomplete="off" :disabled="state.loginBusy" required></label><p class="muted">{{ t('integration.tokenHelp') }}</p><p v-if="state.loginError" class="error-notice" role="alert">{{ displayError(state.loginError).message }}</p><button class="dark-button" :disabled="state.loginBusy || !tokenInput.trim()">{{ t(state.loginBusy ? 'integration.loading' : 'integration.login') }}<AppIcon name="arrow" /></button><div class="language-switcher login-languages" :aria-label="t('language')" role="group"><button v-for="item in supportedLocales" :key="item" type="button" :class="{ selected: locale === item }" :aria-pressed="locale === item" @click="locale = item">{{ item.toUpperCase() }}</button></div></form>
  </div>
  <div v-else class="app-shell">
    <aside class="sidebar"><a href="#overview" class="brand"><span class="brand-mark"><AppIcon name="growth" /></span><span class="brand-copy">Career Quest<span class="brand-subtitle">{{ t('design.platform') }}</span></span></a><p class="sidebar-label">{{ t(state.identity.role === 'hr' ? 'integration.hrAccount' : 'integration.employeeAccount') }}</p><nav :aria-label="t('pages.navigation')"><a v-for="item in nav" :key="item.key" :href="`#${item.key}`" :class="['nav-item', { active: page === item.key || page === 'profile' && item.key === 'overview' }]" :aria-current="page === item.key ? 'page' : undefined"><AppIcon :name="item.icon" /><span>{{ t(item.title) }}</span></a></nav><div class="sidebar-bottom"><a v-for="item in ['help','settings']" :key="item" :href="`#${item}`" :class="['nav-item',{active:page === item}]"><AppIcon :name="item" />{{ t(item) }}</a><button class="nav-item logout-button" @click="logout"><AppIcon name="arrow" />{{ t('integration.logout') }}</button><div class="sidebar-foot"><span>Career Quest</span><span>{{ locale.toUpperCase() }}</span></div></div></aside>
    <main class="content"><header class="topbar"><a class="mobile-brand" href="#overview"><span class="brand-mark"><AppIcon name="growth" /></span>Career Quest</a><div class="breadcrumbs"><a href="#overview">{{ t('home') }}</a><AppIcon name="chevron" /><span>{{ title(page) }}</span></div><div class="top-actions"><div class="language-switcher" role="group" :aria-label="t('language')"><button v-for="item in supportedLocales" :key="item" :class="{ selected: locale === item }" :aria-pressed="locale === item" @click="locale = item">{{ item.toUpperCase() }}</button></div><a class="top-settings" href="#settings" :aria-label="t('settings')"><AppIcon name="settings" /></a><a href="#profile" class="profile-trigger" :aria-label="t('integration.profile')"><span class="avatar avatar-top">{{ initials }}</span><span class="profile-trigger-copy"><strong>{{ state.identity.role === 'hr' ? t('integration.hrAccount') : employee?.full_name || state.identity.employee_id }}</strong><span>{{ t('integration.profile') }}</span></span></a></div></header>
      <nav class="mobile-nav" :aria-label="t('pages.navigation')"><a v-for="item in nav" :key="item.key" :href="`#${item.key}`" :class="{ active: page === item.key }">{{ t(item.title) }}</a><a href="#settings">{{ t('settings') }}</a><a href="#help">{{ t('help') }}</a></nav>
      <div class="page-wrap">
        <section v-if="state.identity.role === 'hr' && ['overview','profile'].includes(page)" class="panel employee-picker"><label>{{ t('integration.selectedEmployee') }}<select :value="state.employeeId" :disabled="locked || state.directoryBusy" @change="session.selectEmployee($event.target.value)"><option v-if="!state.employeeId" value="">{{ t('integration.chooseEmployee') }}</option><option v-for="person in state.employees" :key="person.employee_id" :value="person.employee_id">{{ person.full_name }} · {{ person.employee_id }} · {{ person.role }}</option></select></label><button class="outline-button" :disabled="locked || state.directoryBusy" @click="session.loadDirectory()">{{ t('integration.refresh') }}</button></section>
        <div v-if="state.directoryError" class="error-notice" role="alert">{{ displayError(state.directoryError).message }}<button class="text-button" :disabled="locked || state.directoryBusy" @click="session.loadDirectory()">{{ t('integration.retry') }}</button></div>
        <div v-if="state.catalogError" class="error-notice" role="alert">{{ t('integration.catalogError') }}. {{ displayError(state.catalogError).message }}<button class="text-button" :disabled="state.catalogBusy" @click="session.loadCatalog()">{{ t('integration.retry') }}</button></div>
        <template v-if="['overview','profile'].includes(page)">
          <p v-if="state.profileBusy || state.directoryBusy" class="notice" role="status">{{ t('integration.loading') }}</p>
          <div v-if="state.profileError" class="error-notice" role="alert">{{ displayError(state.profileError).message }}<button class="outline-button" :disabled="state.profileBusy || state.completion.busy" @click="session.refreshEmployee()">{{ t('integration.retry') }}</button></div>
          <EmployeeView v-if="state.profile" :profile="state.profile" :recommendations="state.recommendations" :events="state.events" :skills="state.skills" :loading-recommendations="state.recommendationBusy" :recommendation-error="displayError(state.recommendationError)" :completion="completion" @refresh="session.refreshEmployee()" @complete="session.complete" @retry-completion="session.retryCompletion()" @discard-completion="session.discardCompletion()" />
          <div v-if="!state.profile && state.completion.result" class="notice" role="status"><strong>{{ t('employee.completed') }}: {{ state.completion.result.event_id }}</strong><p>{{ t('employee.newCoverage') }}: {{ state.completion.result.trajectory.progress_pct }}%</p><p>{{ t('integration.refreshPartial') }}</p></div>
          <p v-if="!state.employeeId && !state.directoryBusy" class="empty-state">{{ t('integration.noEmployees') }}</p>
        </template>
        <HrView v-else-if="page === 'hr' && state.identity.role === 'hr'" :overview="state.hr" :employees="state.employees" :busy="state.hrBusy" :error="displayError(state.hrError)" :importing="state.importing || !!state.completion.pending || state.completion.busy" :import-result="state.importResult" :import-error="displayError(state.importError)" :refreshing-after-import="state.refreshingAfterImport" @refresh="session.loadHR()" @select-employee="selectEmployee" @import-files="session.importFiles" />
        <template v-else-if="page === 'catalog'"><p v-if="state.catalogBusy" class="notice" role="status">{{ t('integration.loading') }}</p><CatalogView :events="state.events" :skills="state.skills" /></template>
        <section v-else-if="page === 'settings'" class="panel settings-panel"><h1>{{ t('settings') }}</h1><label>{{ t('integration.preferredLanguage') }}<select v-model="locale"><option v-for="item in supportedLocales" :key="item" :value="item">{{ {ru:'Русский',kk:'Қазақша',en:'English'}[item] }}</option></select></label><p class="body-copy">{{ t('integration.settingsCopy') }}</p><p class="notice">{{ t('integration.serverCopy') }}</p><button class="outline-button spaced" @click="logout">{{ t('integration.logout') }}</button></section>
        <section v-else class="panel"><h1>{{ t('integration.helpIntro') }}</h1><p class="body-copy">{{ t('integration.helpFlow') }}</p><p class="body-copy">{{ t('integration.helpRetry') }}</p><p class="body-copy">{{ t('integration.helpHr') }}</p><p class="notice">{{ t('integration.serverCopy') }}</p></section>
        <div v-if="state.completion.pending && !['overview','profile'].includes(page)" class="notice"><a href="#overview">{{ t('integration.pendingWarning') }}</a></div>
      </div>
    </main>
  </div>
</template>
