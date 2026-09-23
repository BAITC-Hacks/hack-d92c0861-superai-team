<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import AppIcon from './AppIcon.vue'
const props = defineProps({ events: { type: Array, default: () => [] }, skills: { type: Array, default: () => [] } })
const { t, locale } = useI18n()
const query = ref(''), type = ref('all'), format = ref('all')
const skillNames = computed(() => new Map(props.skills.map(skill => [skill.skill_id, skill.name])))
const types = computed(() => [...new Set(props.events.map(event => event.type))])
const results = computed(() => props.events.filter(event => `${event.event_id} ${event.title} ${event.description} ${event.develops_skills.map(skill => `${skill.skill_id} ${skillNames.value.get(skill.skill_id) || ''}`).join(' ')}`.toLocaleLowerCase(locale.value).includes(query.value.trim().toLocaleLowerCase(locale.value)) && (type.value === 'all' || type.value === event.type) && (format.value === 'all' || format.value === event.format)))
function reset() { query.value = ''; type.value = 'all'; format.value = 'all' }
</script>
<template>
  <section class="panel"><h1>{{ t('catalog') }}</h1><p class="body-copy">{{ t('integration.catalogIntro') }}</p><div class="toolbar"><label class="search-field">{{ t('pages.search') }}<input v-model="query" type="search" :placeholder="t('pages.searchEvents')"></label><label>{{ t('pages.type') }}<select v-model="type"><option value="all">{{ t('all') }}</option><option v-for="item in types" :key="item" :value="item">{{ t(`pages.types.${item}`) }}</option></select></label><label>{{ t('pages.format') }}<select v-model="format"><option value="all">{{ t('all') }}</option><option v-for="item in ['online','offline','self_paced']" :key="item" :value="item">{{ t(`pages.formats.${item}`) }}</option></select></label></div><div class="filter-summary"><span role="status">{{ t('pages.results', { count: results.length }) }}</span><button class="text-button" @click="reset">{{ t('pages.reset') }}</button></div></section>
  <div class="activity-grid spaced"><article v-for="event in results" :key="event.event_id" class="activity-card"><div class="activity-top"><span class="activity-icon"><AppIcon name="book" /></span><span class="activity-type">{{ t(`pages.types.${event.type}`) }}</span><span class="activity-id">{{ event.event_id }}</span></div><h3>{{ event.title }}</h3><p class="activity-meta">{{ t('pages.hours', { count: event.duration_hours }) }} · {{ t(`pages.formats.${event.format}`) }}</p><p class="event-description">{{ event.description }}</p><p class="muted">{{ event.format === 'self_paced' ? t('pages.anytime') : event.upcoming_sessions.join(' · ') || t('integration.noSession') }}</p><div class="activity-bottom"><span class="skill-tag">{{ t(event.mandatory ? 'pages.mandatory' : 'pages.optional') }}</span></div></article></div>
  <p v-if="!results.length" class="empty-state">{{ t('integration.noEvents') }}</p><p class="muted spaced">{{ t('integration.readOnlyCatalog') }}</p>
</template>
