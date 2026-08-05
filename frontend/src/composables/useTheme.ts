import { ref } from 'vue'

const STORAGE_KEY = '7x-theme'
const DARK_CLASS = 'app-dark'

function getInitialDark(): boolean {
  const stored = localStorage.getItem(STORAGE_KEY)
  if (stored) return stored === 'dark'
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

const isDark = ref(getInitialDark())

function applyTheme() {
  document.documentElement.classList.toggle(DARK_CLASS, isDark.value)
  localStorage.setItem(STORAGE_KEY, isDark.value ? 'dark' : 'light')
}

applyTheme()

export function useTheme() {
  function toggleTheme() {
    isDark.value = !isDark.value
    applyTheme()
  }

  return { isDark, toggleTheme }
}
