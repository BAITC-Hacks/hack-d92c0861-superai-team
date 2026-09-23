import { watch } from 'vue'
import { createI18n } from 'vue-i18n'
import ru from './locales/ru.json'
import kk from './locales/kk.json'
import en from './locales/en.json'

export const supportedLocales = ['ru', 'kk', 'en']
const storageKey = 'careerquest-language'
const legacyLocales = { kz: 'kk', eng: 'en' }

function initialLocale() {
  try {
    const saved = localStorage.getItem(storageKey)
    const locale = legacyLocales[saved] ?? saved
    return supportedLocales.includes(locale) ? locale : 'ru'
  } catch {
    return 'ru'
  }
}

const i18n = createI18n({
  legacy: false,
  locale: initialLocale(),
  fallbackLocale: 'en',
  messages: { ru, kk, en },
})

watch(i18n.global.locale, (locale) => {
  if (typeof document !== 'undefined') document.documentElement.lang = locale
  try {
    localStorage.setItem(storageKey, locale)
  } catch {
    // Language switching also works when browser storage is unavailable.
  }
}, { immediate: true })

// Dataset translations are keyed by stable IDs; new records keep their source text.
export function translateDatasetField(collection, id, field, originalText) {
  const key = `${collection}.${id}.${field}`
  const { t, te, locale } = i18n.global
  return te(key, locale.value) || te(key, 'en') ? t(key) : originalText
}

export default i18n
