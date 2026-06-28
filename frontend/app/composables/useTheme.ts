import { ref } from 'vue'

export type Theme =
  | 'dark' | 'light'
  | 'sakura' | 'matcha' | 'ocean' | 'amber' | 'cyber' | 'parchment'

export const THEMES: { id: Theme; label: string; accent: string }[] = [
  { id: 'dark',      label: '暗黑', accent: '#7c6af7' },
  { id: 'light',     label: '亮色', accent: '#7c6af7' },
  { id: 'sakura',    label: '樱花', accent: '#d44880' },
  { id: 'matcha',    label: '抹茶', accent: '#2d7a50' },
  { id: 'ocean',     label: '海洋', accent: '#2060b0' },
  { id: 'amber',     label: '琥珀', accent: '#b06820' },
  { id: 'cyber',     label: '赛博', accent: '#a060ff' },
  { id: 'parchment', label: '书卷', accent: '#8b6a3e' },
]

const theme = ref<Theme>('dark')

export function useTheme() {
  function apply(t: Theme) {
    theme.value = t
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', t)
      localStorage.setItem('theme', t)
    }
  }

  function init() {
    const saved = typeof localStorage !== 'undefined'
      ? (localStorage.getItem('theme') as Theme | null)
      : null
    apply(saved ?? 'dark')
  }

  return { theme, THEMES, init, apply }
}
