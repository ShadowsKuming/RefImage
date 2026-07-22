<template>
  <div class="login-wrap">
    <div class="login-card">
      <h1 class="logo">RefImage</h1>
      <p class="sub">输入邀请 Token 登录</p>

      <input
        v-model="tokenInput"
        type="text"
        class="token-input"
        placeholder="粘贴 Token"
        autocomplete="off"
        @keydown.enter="login"
      />

      <button class="login-btn" :disabled="loading || !tokenInput" @click="login">
        {{ loading ? '验证中…' : '进入' }}
      </button>

      <p v-if="error" class="error-msg">{{ error }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
definePageMeta({ ssr: false, layout: false })

const tokenInput = ref('')
const loading = ref(false)
const error = ref('')

const { setToken } = useAuth()
const { init } = useTheme()
const config = useRuntimeConfig()

onMounted(() => init())

async function login() {
  if (!tokenInput.value) return
  error.value = ''
  loading.value = true
  try {
    const r = await fetch(`${config.public.apiBase}/auth/me`, {
      headers: { Authorization: `Bearer ${tokenInput.value}` },
    })
    if (!r.ok) {
      error.value = 'Token 无效，请重新输入'
      return
    }
    setToken(tokenInput.value)
    await navigateTo('/')
  } catch {
    error.value = '无法连接服务器'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg);
}

.login-card {
  width: 360px;
  padding: 40px 32px 36px;
  background: var(--surface);
  border: 1px solid var(--border-md);
  border-radius: 16px;
  box-shadow: 0 8px 32px var(--shadow);
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.logo {
  margin: 0;
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.5px;
}

.sub {
  margin: -8px 0 4px;
  font-size: 0.85rem;
  color: var(--text-muted);
}

.token-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 14px;
  background: var(--surface-inset);
  border: 1px solid var(--border-md);
  border-radius: 8px;
  color: var(--text);
  font-size: 0.95rem;
  outline: none;
  transition: border-color 0.2s;
}
.token-input:focus { border-color: var(--border-focus); }

.login-btn {
  padding: 10px;
  border: none;
  border-radius: 8px;
  background: var(--accent);
  color: #fff;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
.login-btn:disabled { opacity: 0.45; cursor: default; }
.login-btn:not(:disabled):hover { background: var(--accent-hover); }

.error-msg {
  margin: 0;
  font-size: 0.82rem;
  color: var(--error);
  text-align: center;
}
</style>
