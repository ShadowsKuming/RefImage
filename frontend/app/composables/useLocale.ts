import { ref } from 'vue'
import { LOCALES, LOCALE_META, type Locale } from '../locales'

export type { Locale }
export { LOCALE_META }

const locale = ref<Locale>('zh')

function resolve(dict: Record<string, any>, key: string): unknown {
  return key.split('.').reduce<any>((acc, part) => (acc && typeof acc === 'object' ? acc[part] : undefined), dict)
}

export function useLocale() {
  function t(key: string, vars?: Record<string, string | number>): string {
    let value = resolve(LOCALES[locale.value], key)
    if (value === undefined) {
      if (import.meta.dev) console.warn(`[i18n] missing key "${key}" for locale "${locale.value}"`)
      value = resolve(LOCALES.zh, key) ?? key
    }
    let result = typeof value === 'string' ? value : key
    if (vars) {
      for (const [k, v] of Object.entries(vars)) {
        result = result.replaceAll(`{${k}}`, String(v))
      }
    }
    return result
  }

  function apply(l: Locale) {
    locale.value = l
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('lang', l)
      localStorage.setItem('locale', l)
    }
  }

  function init() {
    const saved = typeof localStorage !== 'undefined'
      ? (localStorage.getItem('locale') as Locale | null)
      : null
    apply(saved ?? 'zh')
  }

  return { locale, LOCALE_META, t, init, apply }
}
