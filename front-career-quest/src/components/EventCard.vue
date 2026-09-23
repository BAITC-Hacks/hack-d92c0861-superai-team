<script setup>
import { useI18n } from 'vue-i18n'
import { translateDatasetField } from '../i18n'
defineProps({ event: { type: Object, required: true }, planned: Boolean })
defineEmits(['details'])
const { t } = useI18n()
</script>
<template>
  <article class="activity-card">
    <div class="activity-top"><span class="activity-icon teal">✦</span><span class="activity-type">{{ t(`pages.types.${event.type}`) }}</span><span class="activity-id">{{ event.event_id }}</span></div>
    <h3>{{ translateDatasetField('events', event.event_id, 'title', event.title) }}</h3>
    <p class="activity-meta">{{ t('pages.hours', { count: event.duration_hours }) }} · {{ t(`pages.formats.${event.format}`) }}</p>
    <p class="event-description">{{ translateDatasetField('events', event.event_id, 'description', event.description) }}</p>
    <div class="activity-bottom"><span class="skill-tag">{{ t(event.mandatory ? 'pages.mandatory' : planned ? 'pages.inPlan' : 'pages.optional') }}</span><button class="enroll-button" @click="$emit('details', event)">{{ t('details') }}</button></div>
  </article>
</template>
