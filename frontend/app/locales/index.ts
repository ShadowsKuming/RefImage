import zh from './zh'
import en from './en'
import ja from './ja'
import pt from './pt'

export type { Dict } from './zh'
export type Locale = 'zh' | 'en' | 'ja' | 'pt'

export const LOCALES: Record<Locale, typeof zh> = { zh, en, ja, pt }

export const LOCALE_META: { id: Locale; label: string }[] = [
  { id: 'zh', label: '中文' },
  { id: 'en', label: 'English' },
  { id: 'ja', label: '日本語' },
  { id: 'pt', label: 'Português' },
]
