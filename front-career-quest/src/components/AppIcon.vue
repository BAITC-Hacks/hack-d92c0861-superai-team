<script setup>
import { computed } from 'vue'

const props = defineProps({ name: { type: String, default: 'arrow' } })
const paths = {
  overview: ['M3 10.5 12 3l9 7.5', 'M5 9v11h5v-6h4v6h5V9'],
  path: ['M4 19h3a4 4 0 0 0 4-4v-6a4 4 0 0 1 4-4h5', 'm16 1 4 4-4 4', 'M4 16v6'],
  catalog: ['M3 3h7v7H3z', 'M14 3h7v7h-7z', 'M3 14h7v7H3z', 'M14 14h7v7h-7z'],
  team: ['M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2', 'M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0', 'M22 21v-2a4 4 0 0 0-3-3.87', 'M16 3.13a4 4 0 0 1 0 7.75'],
  help: ['M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0', 'M9.1 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3', 'M12 17h.01'],
  settings: ['M19.36 9.75 L21.82 10.09 L21.82 13.91 L19.36 14.25 L18.80 15.61 L20.29 17.59 L17.59 20.29 L15.61 18.80 L14.25 19.36 L13.91 21.82 L10.09 21.82 L9.75 19.36 L8.39 18.80 L6.41 20.29 L3.71 17.59 L5.20 15.61 L4.64 14.25 L2.18 13.91 L2.18 10.09 L4.64 9.75 L5.20 8.39 L3.71 6.41 L6.41 3.71 L8.39 5.20 L9.75 4.64 L10.09 2.18 L13.91 2.18 L14.25 4.64 L15.61 5.20 L17.59 3.71 L20.29 6.41 L18.80 8.39Z', 'M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0'],
  user: ['M20 21v-2a6 6 0 0 0-6-6h-4a6 6 0 0 0-6 6v2', 'M16 5a4 4 0 1 1-8 0 4 4 0 0 1 8 0'],
  arrow: ['M4 12h16', 'm14 6 6 6-6 6'],
  download: ['M12 3v12', 'm7 10 5 5 5-5', 'M5 16v5h14v-5'],
  book: ['M12 5v16', 'M12 5C9 3 5 3 2 4v15c3-1 7-1 10 2 3-3 7-3 10-2V4c-3-1-7-1-10 1Z'],
  award: ['M17 8a5 5 0 1 1-10 0 5 5 0 0 1 10 0', 'm8 12-2 9 6-3 6 3-2-9'],
  briefcase: ['M3 7h18v14H3z', 'M8 7V3h8v4', 'M3 12a21 21 0 0 0 18 0', 'M10 13v3h4v-3'],
  check: ['m5 12 4 4L19 6'],
  clock: ['M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0', 'M12 6v6l4 2'],
  search: ['M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0', 'm15 15 6 6'],
  chevron: ['m9 5 7 7-7 7'],
  growth: ['M5 19v-5', 'M12 19V9', 'M19 19V4', 'M3 5h5', 'M5.5 2.5v5'],
  target: ['M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0', 'M17 12a5 5 0 1 1-10 0 5 5 0 0 1 10 0', 'M12 12h.01'],
  close: ['m6 6 12 12', 'M18 6 6 18'],
}
const strokes = computed(() => paths[props.name] || paths.arrow)
</script>

<template>
  <svg class="shell-icon" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path v-for="(path, index) in strokes" :key="index" :d="path" />
  </svg>
</template>
