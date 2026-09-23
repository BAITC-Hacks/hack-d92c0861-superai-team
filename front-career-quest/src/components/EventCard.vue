<script setup>
import { useI18n } from 'vue-i18n'
import { translateDatasetField } from '../i18n'
import AppIcon from './AppIcon.vue'
defineProps({ event: { type: Object, required: true }, planned: Boolean })
defineEmits(['details'])
const { t } = useI18n()
const icons = { course: 'book', mentoring: 'team', workshop: 'briefcase', certification: 'award', meetup: 'team', onboarding: 'user', compliance: 'check' }
</script>
<template>
  <article class="activity-card" :data-type="event.type">
    <div class="activity-top">
      <span class="activity-icon"><AppIcon :name="icons[event.type] || 'book'" /></span>
      <span class="activity-type">{{ t(`pages.types.${event.type}`) }}</span>
      <span class="activity-id">{{ event.event_id }}</span>
    </div>
    <h3>{{ translateDatasetField('events', event.event_id, 'title', event.title) }}</h3>
    <p class="activity-meta"><AppIcon name="clock" />{{ t('pages.hours', { count: event.duration_hours }) }}<span class="meta-dot">·</span>{{ t(`pages.formats.${event.format}`) }}</p>
    <p class="event-description">{{ translateDatasetField('events', event.event_id, 'description', event.description) }}</p>
    <div class="activity-bottom">
      <span class="skill-tag" :class="{ 'tag-planned': planned }"><AppIcon v-if="planned" name="check" />{{ t(event.mandatory ? 'pages.mandatory' : planned ? 'pages.inPlan' : 'pages.optional') }}</span>
      <button class="enroll-button" :aria-label="`${t('design.viewActivity')}: ${translateDatasetField('events', event.event_id, 'title', event.title)}`" @click="$emit('details', event)">{{ t('design.viewActivity') }}<AppIcon name="arrow" /></button>
    </div>
  </article>
</template>
