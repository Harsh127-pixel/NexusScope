<template>
  <div class="auth-root">
    <!-- Background grid + glow -->
    <div class="auth-bg">
      <div class="auth-glow" />
    </div>

    <div class="auth-card-wrap">
      <!-- Logo -->
      <div class="auth-logo q-mb-xl">
        <svg width="36" height="36" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
          <circle cx="12" cy="12" r="2" fill="currentColor"/>
          <path d="M12 3V5M12 19V21M3 12H5M19 12H21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        <span class="auth-wordmark">NEXUS<span>SCOPE</span></span>
      </div>

      <!-- Card -->
      <div class="auth-card">
        <!-- Tab Header -->
        <div class="auth-tabs" v-if="mode !== 'forgot'">
          <button
            class="auth-tab"
            :class="{ 'auth-tab--active': mode === 'login' }"
            @click="switchMode('login')"
            id="tab-login"
          >SIGN IN</button>
          <button
            class="auth-tab"
            :class="{ 'auth-tab--active': mode === 'register' }"
            @click="switchMode('register')"
            id="tab-register"
          >SIGN UP</button>
        </div>

        <!-- ── SIGN IN ──────────────────────────────────────────── -->
        <transition name="slide-fade" mode="out-in">
          <div v-if="mode === 'login'" key="login" class="auth-form">
            <p class="auth-subtitle">Intelligence access requires authentication.</p>

            <!-- Google Button -->
            <button class="google-btn" @click="handleGoogle" :disabled="busy" id="btn-google-signin">
              <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
              <span>{{ busy ? 'Signing in…' : 'Continue with Google' }}</span>
            </button>

            <div class="auth-divider"><span>OR</span></div>

            <q-form @submit="handleLogin">
              <div class="auth-field-wrap">
                <label class="auth-label">EMAIL</label>
                <q-input
                  v-model="form.email"
                  type="email"
                  filled dark dense
                  placeholder="agent@nexusscope.com"
                  class="auth-input"
                  :rules="[v => !!v || 'Required', v => /.+@.+/.test(v) || 'Invalid email']"
                  id="input-email-login"
                />
              </div>
              <div class="auth-field-wrap q-mt-sm">
                <div class="row justify-between items-center">
                  <label class="auth-label">PASSWORD</label>
                  <button type="button" class="auth-link" @click="switchMode('forgot')" id="btn-forgot">Forgot password?</button>
                </div>
                <q-input
                  v-model="form.password"
                  :type="showPwd ? 'text' : 'password'"
                  filled dark dense
                  placeholder="••••••••"
                  class="auth-input"
                  :rules="[v => !!v || 'Required']"
                  id="input-password-login"
                >
                  <template v-slot:append>
                    <q-btn flat dense round @click="showPwd = !showPwd" :icon="showPwd ? 'visibility_off' : 'visibility'" size="sm" />
                  </template>
                </q-input>
              </div>

              <div v-if="authStore.error" class="auth-error q-mt-sm">
                <span>⚠ {{ authStore.error }}</span>
              </div>

              <q-btn
                type="submit"
                class="auth-submit-btn q-mt-lg full-width"
                :loading="busy"
                id="btn-submit-login"
              >
                <Zap :size="16" class="q-mr-sm" />
                AUTHENTICATE
              </q-btn>
            </q-form>
          </div>

          <!-- ── SIGN UP ──────────────────────────────────────────── -->
          <div v-else-if="mode === 'register'" key="register" class="auth-form">
            <p class="auth-subtitle">Create your NexusScope analyst account.</p>

            <button class="google-btn" @click="handleGoogle" :disabled="busy" id="btn-google-signup">
              <svg width="18" height="18" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>
              <span>{{ busy ? 'Creating account…' : 'Sign up with Google' }}</span>
            </button>

            <div class="auth-divider"><span>OR</span></div>

            <q-form @submit="handleRegister">
              <div class="auth-field-wrap">
                <label class="auth-label">EMAIL</label>
                <q-input
                  v-model="form.email"
                  type="email"
                  filled dark dense
                  placeholder="agent@nexusscope.com"
                  class="auth-input"
                  :rules="[v => !!v || 'Required', v => /.+@.+\..+/.test(v) || 'Invalid email']"
                  id="input-email-register"
                />
              </div>
              <div class="auth-field-wrap q-mt-sm">
                <label class="auth-label">PASSWORD</label>
                <q-input
                  v-model="form.password"
                  :type="showPwd ? 'text' : 'password'"
                  filled dark dense
                  placeholder="Min. 6 characters"
                  class="auth-input"
                  :rules="[v => !!v || 'Required', v => v.length >= 6 || 'Min 6 chars']"
                  id="input-password-register"
                >
                  <template v-slot:append>
                    <q-btn flat dense round @click="showPwd = !showPwd" :icon="showPwd ? 'visibility_off' : 'visibility'" size="sm" />
                  </template>
                </q-input>
              </div>
              <div class="auth-field-wrap q-mt-sm">
                <label class="auth-label">CONFIRM PASSWORD</label>
                <q-input
                  v-model="form.confirm"
                  :type="showPwd ? 'text' : 'password'"
                  filled dark dense
                  placeholder="Repeat password"
                  class="auth-input"
                  :rules="[v => !!v || 'Required', v => v === form.password || 'Passwords do not match']"
                  id="input-confirm-register"
                />
              </div>

              <!-- Password strength bar -->
              <div class="pwd-strength q-mt-xs">
                <div class="pwd-strength-bar" :style="{ width: pwdStrengthPct + '%', background: pwdStrengthColor }" />
              </div>
              <div class="auth-label q-mt-xs" :style="{ color: pwdStrengthColor }">{{ pwdStrengthLabel }}</div>

              <div v-if="authStore.error" class="auth-error q-mt-sm">
                <span>⚠ {{ authStore.error }}</span>
              </div>

              <q-btn
                type="submit"
                class="auth-submit-btn q-mt-lg full-width"
                :loading="busy"
                id="btn-submit-register"
              >
                <Shield :size="16" class="q-mr-sm" />
                CREATE ACCOUNT
              </q-btn>
            </q-form>
          </div>

          <!-- ── FORGOT PASSWORD ──────────────────────────────────── -->
          <div v-else-if="mode === 'forgot'" key="forgot" class="auth-form">
            <div class="auth-back-btn q-mb-md" @click="switchMode('login')" id="btn-back-login">
              <ChevronLeft :size="16" /> BACK TO SIGN IN
            </div>
            <h2 class="auth-form-title">Reset Password</h2>
            <p class="auth-subtitle">Enter your email and we'll send a secure reset link.</p>

            <q-form @submit="handleForgot">
              <div class="auth-field-wrap">
                <label class="auth-label">EMAIL ADDRESS</label>
                <q-input
                  v-model="form.email"
                  type="email"
                  filled dark dense
                  placeholder="agent@nexusscope.com"
                  class="auth-input"
                  :rules="[v => !!v || 'Required', v => /.+@.+/.test(v) || 'Invalid email']"
                  id="input-email-forgot"
                />
              </div>

              <div v-if="authStore.error" class="auth-error q-mt-sm">
                <span>⚠ {{ authStore.error }}</span>
              </div>

              <div v-if="resetSent" class="auth-success q-mt-sm">
                <span>✓ Reset link sent! Check your inbox.</span>
              </div>

              <q-btn
                type="submit"
                class="auth-submit-btn q-mt-lg full-width"
                :loading="busy"
                id="btn-submit-forgot"
              >
                <Mail :size="16" class="q-mr-sm" />
                SEND RESET LINK
              </q-btn>
            </q-form>
          </div>
        </transition>
      </div>

      <!-- Footer -->
      <p class="auth-footer">
        NexusScope OSINT Platform · Protected by Firebase Auth
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useQuasar } from 'quasar'
import { Zap, Shield, Mail, ChevronLeft } from 'lucide-vue-next'
import { useAuthStore } from 'src/stores/authStore'

const $q        = useQuasar()
const authStore = useAuthStore()

type Mode = 'login' | 'register' | 'forgot'
const mode     = ref<Mode>('login')
const busy     = ref(false)
const showPwd  = ref(false)
const resetSent = ref(false)

const form = reactive({ email: '', password: '', confirm: '' })

function switchMode(m: Mode) {
  mode.value = m
  form.email = form.password = form.confirm = ''
  resetSent.value = false
  authStore.clearError()
}

// ── Password strength ──────────────────────────────────────────────────────
const pwdStrengthPct = computed(() => {
  const p = form.password
  if (!p) return 0
  let score = 0
  if (p.length >= 6)  score += 25
  if (p.length >= 10) score += 25
  if (/[A-Z]/.test(p)) score += 25
  if (/[^A-Za-z0-9]/.test(p)) score += 25
  return score
})

const pwdStrengthColor = computed(() => {
  const s = pwdStrengthPct.value
  if (s <= 25) return '#ef4444'
  if (s <= 50) return '#f97316'
  if (s <= 75) return '#eab308'
  return '#22c55e'
})

const pwdStrengthLabel = computed(() => {
  const s = pwdStrengthPct.value
  if (!s) return ''
  if (s <= 25) return 'WEAK'
  if (s <= 50) return 'FAIR'
  if (s <= 75) return 'GOOD'
  return 'STRONG'
})

// ── Handlers ───────────────────────────────────────────────────────────────
async function handleLogin() {
  busy.value = true
  try {
    await authStore.login(form.email, form.password)
    $q.notify({ type: 'positive', message: 'Authentication successful', position: 'top' })
  } catch { /* error shown via store */ } finally { busy.value = false }
}

async function handleRegister() {
  busy.value = true
  try {
    await authStore.register(form.email, form.password)
    $q.notify({ type: 'positive', message: 'Account created. Welcome, Analyst.', position: 'top' })
  } catch { /* error shown via store */ } finally { busy.value = false }
}

async function handleGoogle() {
  busy.value = true
  try {
    await authStore.loginGoogle()
    $q.notify({ type: 'positive', message: 'Authenticated via Google', position: 'top' })
  } catch { /* error shown via store */ } finally { busy.value = false }
}

async function handleForgot() {
  busy.value = true
  try {
    await authStore.forgotPassword(form.email)
    resetSent.value = true
  } catch { /* error shown via store */ } finally { busy.value = false }
}
</script>

<style scoped>
/* ── Root ──────────────────────────────────────────────────────────────────── */
.auth-root {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #070b0f;
  position: relative;
  overflow: hidden;
  font-family: 'Inter', 'Roboto', sans-serif;
}

.auth-bg {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(rgba(0,212,255,0.04) 1px, transparent 1px);
  background-size: 28px 28px;
}

.auth-glow {
  position: absolute;
  top: -200px;
  left: 50%;
  transform: translateX(-50%);
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(0,212,255,0.12) 0%, transparent 70%);
  pointer-events: none;
}

/* ── Wrapper ─────────────────────────────────────────────────────────────── */
.auth-card-wrap {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* ── Logo ────────────────────────────────────────────────────────────────── */
.auth-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #00d4ff;
}

.auth-wordmark {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #fff;
}

.auth-wordmark span { color: #00d4ff; }

/* ── Card ────────────────────────────────────────────────────────────────── */
.auth-card {
  width: 100%;
  background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 20px;
  backdrop-filter: blur(20px);
  overflow: hidden;
  box-shadow: 0 25px 80px rgba(0,0,0,0.6), 0 0 0 1px rgba(0,212,255,0.05);
}

/* ── Tabs ────────────────────────────────────────────────────────────────── */
.auth-tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid rgba(255,255,255,0.07);
}

.auth-tab {
  padding: 16px;
  background: none;
  border: none;
  color: rgba(255,255,255,0.35);
  font-family: 'Roboto Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border-bottom: 2px solid transparent;
}

.auth-tab:hover { color: rgba(255,255,255,0.6); }

.auth-tab--active {
  color: #00d4ff;
  border-bottom-color: #00d4ff;
  background: rgba(0,212,255,0.05);
}

/* ── Form area ───────────────────────────────────────────────────────────── */
.auth-form { padding: 28px; }

.auth-subtitle {
  font-size: 13px;
  color: rgba(255,255,255,0.4);
  margin: 0 0 20px;
}

.auth-form-title {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 6px;
}

/* ── Google Button ───────────────────────────────────────────────────────── */
.google-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 11px 16px;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: 10px;
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.google-btn:hover:not(:disabled) {
  background: rgba(255,255,255,0.1);
  border-color: rgba(255,255,255,0.2);
  transform: translateY(-1px);
}

.google-btn:disabled { opacity: 0.5; cursor: not-allowed; }

/* ── Divider ─────────────────────────────────────────────────────────────── */
.auth-divider {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 18px 0;
  color: rgba(255,255,255,0.2);
  font-size: 11px;
  font-family: 'Roboto Mono', monospace;
  letter-spacing: 0.1em;
}

.auth-divider::before,
.auth-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: rgba(255,255,255,0.08);
}

/* ── Field label ─────────────────────────────────────────────────────────── */
.auth-label {
  display: block;
  font-size: 10px;
  font-family: 'Roboto Mono', monospace;
  letter-spacing: 0.12em;
  color: rgba(255,255,255,0.4);
  margin-bottom: 6px;
}

/* ── Submit button ───────────────────────────────────────────────────────── */
.auth-submit-btn {
  background: linear-gradient(135deg, #0099bb, #00d4ff) !important;
  color: #000 !important;
  font-family: 'Roboto Mono', monospace;
  font-size: 12px;
  letter-spacing: 0.12em;
  font-weight: 700;
  border-radius: 10px;
  padding: 12px;
  transition: all 0.2s !important;
}

.auth-submit-btn:hover { filter: brightness(1.12); transform: translateY(-1px); }

/* ── Inline links ────────────────────────────────────────────────────────── */
.auth-link {
  background: none;
  border: none;
  color: #00d4ff;
  font-size: 11px;
  font-family: 'Roboto Mono', monospace;
  cursor: pointer;
  padding: 0;
  opacity: 0.8;
  transition: opacity 0.2s;
}
.auth-link:hover { opacity: 1; }

.auth-back-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  color: rgba(255,255,255,0.4);
  font-size: 11px;
  font-family: 'Roboto Mono', monospace;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: color 0.2s;
}
.auth-back-btn:hover { color: #00d4ff; }

/* ── Error / Success alert ───────────────────────────────────────────────── */
.auth-error {
  background: rgba(239,68,68,0.1);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: 8px;
  padding: 10px 14px;
  color: #fca5a5;
  font-size: 12px;
}

.auth-success {
  background: rgba(34,197,94,0.1);
  border: 1px solid rgba(34,197,94,0.3);
  border-radius: 8px;
  padding: 10px 14px;
  color: #86efac;
  font-size: 12px;
}

/* ── Password strength ───────────────────────────────────────────────────── */
.pwd-strength {
  height: 3px;
  background: rgba(255,255,255,0.08);
  border-radius: 999px;
  overflow: hidden;
}

.pwd-strength-bar {
  height: 100%;
  border-radius: 999px;
  transition: width 0.3s ease, background 0.3s ease;
}

/* ── Footer ──────────────────────────────────────────────────────────────── */
.auth-footer {
  margin-top: 24px;
  font-size: 11px;
  color: rgba(255,255,255,0.18);
  font-family: 'Roboto Mono', monospace;
  text-align: center;
}

/* ── Transitions ─────────────────────────────────────────────────────────── */
.slide-fade-enter-active { transition: all 0.2s ease; }
.slide-fade-leave-active { transition: all 0.15s ease; }
.slide-fade-enter-from { opacity: 0; transform: translateY(8px); }
.slide-fade-leave-to  { opacity: 0; transform: translateY(-6px); }
</style>
