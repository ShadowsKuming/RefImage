import zh from './zh'
import en from './en'
import ja from './ja'

export type { Dict } from './zh'
export type Locale = 'zh' | 'en' | 'ja'

export const LOCALES: Record<Locale, typeof zh> = { zh, en, ja }

export const LOCALE_META: { id: Locale; label: string }[] = [
  { id: 'zh', label: '中文' },
  { id: 'en', label: 'English' },
  { id: 'ja', label: '日本語' },
]
