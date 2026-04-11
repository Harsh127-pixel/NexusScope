// src/stores/authStore.ts
// Pinia store — wraps Firebase auth state, exposes user profile.

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  auth, signUpEmail, signInEmail, signInGoogle, resetPassword, logOut,
  upsertUserProfile, getUserProfile, onAuthStateChanged,
  type User, type UserProfile,
} from 'src/services/firebase'

export const useAuthStore = defineStore('auth', () => {
  const router = useRouter()

  // ── State ──────────────────────────────────────────────────────────────────
  const user          = ref<User | null>(null)
  const profile       = ref<UserProfile | null>(null)
  const loading       = ref(true)   // true until first onAuthStateChanged fires
  const error         = ref<string | null>(null)
  const isInitialised = ref(false)

  // ── Getters ────────────────────────────────────────────────────────────────
  const isLoggedIn    = computed(() => !!user.value)
  const displayName   = computed(() => profile.value?.displayName ?? user.value?.displayName ?? 'Agent')
  const avatarUrl     = computed(() => profile.value?.photoURL ?? null)
  const userEmail     = computed(() => user.value?.email ?? '')
  const userRole      = computed(() => profile.value?.role ?? 'analyst')

  // ── Init — called once from boot file ──────────────────────────────────────
  function init() {
    onAuthStateChanged(auth, async (firebaseUser) => {
      user.value  = firebaseUser
      loading.value = false
      isInitialised.value = true

      if (firebaseUser) {
        profile.value = await getUserProfile(firebaseUser.uid)
      } else {
        profile.value = null
      }
    })
  }

  // ── Actions ────────────────────────────────────────────────────────────────
  function clearError() { error.value = null }

  async function register(email: string, password: string) {
    error.value = null
    try {
      const u = await signUpEmail(email, password)
      user.value = u
      profile.value = await getUserProfile(u.uid)
      router.push('/')
    } catch (e: any) {
      error.value = _friendlyError(e.code)
      throw e
    }
  }

  async function login(email: string, password: string) {
    error.value = null
    try {
      const u = await signInEmail(email, password)
      user.value = u
      profile.value = await getUserProfile(u.uid)
      router.push('/')
    } catch (e: any) {
      error.value = _friendlyError(e.code)
      throw e
    }
  }

  async function loginGoogle() {
    error.value = null
    try {
      const u = await signInGoogle()
      user.value = u
      profile.value = await getUserProfile(u.uid)
      router.push('/')
    } catch (e: any) {
      error.value = _friendlyError(e.code)
      throw e
    }
  }

  async function forgotPassword(email: string) {
    error.value = null
    try {
      await resetPassword(email)
    } catch (e: any) {
      error.value = _friendlyError(e.code)
      throw e
    }
  }

  async function logout() {
    await logOut()
    user.value = null
    profile.value = null
    router.push('/auth/login')
  }

  // ── Error translator ───────────────────────────────────────────────────────
  function _friendlyError(code: string): string {
    const map: Record<string, string> = {
      'auth/email-already-in-use':    'An account with this email already exists.',
      'auth/invalid-email':           'Invalid email address format.',
      'auth/weak-password':           'Password must be at least 6 characters.',
      'auth/user-not-found':          'No account found with this email.',
      'auth/wrong-password':          'Incorrect password. Try again.',
      'auth/too-many-requests':       'Too many attempts. Account temporarily locked.',
      'auth/popup-closed-by-user':    'Google sign-in was cancelled.',
      'auth/network-request-failed':  'Network error. Check your connection.',
      'auth/user-disabled':           'This account has been disabled.',
    }
    return map[code] ?? `Auth error: ${code}`
  }

  return {
    user, profile, loading, error, isInitialised,
    isLoggedIn, displayName, avatarUrl, userEmail, userRole,
    init, register, login, loginGoogle, forgotPassword, logout, clearError,
  }
})
