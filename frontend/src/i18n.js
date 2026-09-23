import { watch } from 'vue'
import { createI18n } from 'vue-i18n'
import ru from './locales/ru.json'
import kk from './locales/kk.json'
import en from './locales/en.json'
import integration from './locales/integration.js'
import employee from './locales/employee.js'
import hr from './locales/hr.js'
export const supportedLocales = ['ru', 'kk', 'en']
const storageKey = 'careerquest-language'
function initialLocale() {
  try {
    const saved = localStorage.getItem(storageKey)
    const locale = ({ kz: 'kk', eng: 'en' })[saved] || saved
    return supportedLocales.includes(locale) ? locale : 'ru'
  } catch { return 'ru' }
}
const messages = Object.fromEntries(Object.entries({ ru, kk, en }).map(([locale, base]) => [locale, {
  ...base, integration: integration[locale], employee: employee[locale], hr: hr[locale],
}]))
const i18n = createI18n({ legacy: false, locale: initialLocale(), fallbackLocale: 'en', messages })
watch(i18n.global.locale, locale => {
  if (typeof document !== 'undefined') document.documentElement.lang = locale
  try { localStorage.setItem(storageKey, locale) } catch { /* Language persistence is optional. */ }
}, { immediate: true })
export default i18n
