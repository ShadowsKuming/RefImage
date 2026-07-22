export const useAuth = () => {
  const token = useCookie<string | null>('refimg_token', { maxAge: 60 * 60 * 24 * 30 })
  const isLoggedIn = computed(() => !!token.value)

  function setToken(t: string) { token.value = t }
  function clearToken() { token.value = null }

  return { token, isLoggedIn, setToken, clearToken }
}
