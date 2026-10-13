/// <reference types="vite/client" />
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

/* UI language: one per instance, set by the admin in Admin space; the browser keeps a copy to
   avoid flicker on load. Texts live in src/locales/<lang>/<namespace>.json,
   a namespace is a UI area, the key in code is t('namespace:key') */
export const LANGS = ['ru', 'en'] as const
export type Lang = typeof LANGS[number]
export const LANG_TITLES: Record<Lang, string> = { ru: 'Русский', en: 'English' }

const LANG_KEY = 'pa_lang'

const files = import.meta.glob('./locales/*/*.json', { eager: true }) as Record<string, { default: Record<string, unknown> }>
const resources: Record<string, Record<string, Record<string, unknown>>> = {}
for (const [path, mod] of Object.entries(files)) {
  const m = path.match(/\.\/locales\/([a-z]+)\/([\w-]+)\.json$/)
  if (m) (resources[m[1]] ||= {})[m[2]] = mod.default
}

function startLang(): Lang {
  try {
    const saved = localStorage.getItem(LANG_KEY)
    if (saved && (LANGS as readonly string[]).includes(saved)) return saved as Lang
  } catch { /* private mode */ }
  // until the server first responds — the browser language
  return (navigator.language || '').toLowerCase().startsWith('ru') ? 'ru' : 'en'
}

void i18n.use(initReactI18next).init({
  resources,
  lng: startLang(),
  fallbackLng: 'en',
  defaultNS: 'common',
  ns: Object.keys(resources.ru || {}),
  interpolation: { escapeValue: false },
  returnNull: false,
})
document.documentElement.lang = i18n.language

export const lang = () => (i18n.resolvedLanguage || i18n.language || 'en') as Lang
// locale for dates and numbers: toLocaleString(locale())
export const locale = () => (lang() === 'en' ? 'en-US' : 'ru-RU')

export function setLang(next: Lang) {
  try { localStorage.setItem(LANG_KEY, next) } catch { /* private mode */ }
  document.documentElement.lang = next
  void i18n.changeLanguage(next)
}

fetch('/api/lang')
  .then(r => (r.ok ? r.json() : null))
  .then(r => {
    if (r && (LANGS as readonly string[]).includes(r.lang) && r.lang !== i18n.language) setLang(r.lang)
  })
  .catch(() => {})

export default i18n
