import { createApp } from 'vue'
import App from './App.vue'
import i18n from './i18n.js'
import './assets/main.css'
import './assets/integration.css'
createApp(App).use(i18n).mount('#app')
