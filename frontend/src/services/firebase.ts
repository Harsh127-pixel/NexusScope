// src/services/firebase.ts
// Firebase client SDK — initialised once, imported everywhere.

import { initializeApp, getApps, getApp } from 'firebase/app'
import { getAnalytics } from 'firebase/analytics'
import {
  getAuth,
  GoogleAuthProvider,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  sendPasswordResetEmail,
  signOut,
  fetchSignInMethodsForEmail,
  linkWithCredential,
  EmailAuthProvider,
  onAuthStateChanged,
  type User,
} from 'firebase/auth'
import { getFirestore, doc, setDoc, getDoc, updateDoc, serverTimestamp } from 'firebase/firestore'

// ── Firebase Config (public keys only — safe to commit) ──────────────────────
const firebaseConfig = {
  apiKey:            import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain:        import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId:         import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket:     import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId:             import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId:     import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
}

// Avoid duplicate initialisation during HMR
const firebaseApp = getApps().length ? getApp() : initializeApp(firebaseConfig)

export const auth  = getAuth(firebaseApp)
export const db    = getFirestore(firebaseApp)
export const analytics = getAnalytics(firebaseApp)
export const googleProvider = new GoogleAuthProvider()
googleProvider.setCustomParameters({ prompt: 'select_account' })

// ── User Profile in Firestore ─────────────────────────────────────────────────
export interface UserProfile {
  uid:         string
  email:       string
  displayName: string
  photoURL:    string | null
  provider:    string        // 'email' | 'google.com'
  providers:   string[]      // all linked providers
  createdAt:   any
  lastLogin:   any
  role:        'analyst' | 'admin'
}

export async function upsertUserProfile(user: User): Promise<UserProfile> {
  const ref  = doc(db, 'users', user.uid)
  const snap = await getDoc(ref)

  const providers = user.providerData.map(p => p.providerId)
  const primaryProvider = providers.includes('google.com') ? 'google.com' : 'email'

  if (!snap.exists()) {
    // New user — create profile
    const profile: UserProfile = {
      uid:         user.uid,
      email:       user.email ?? '',
      displayName: user.displayName ?? user.email?.split('@')[0] ?? 'Agent',
      photoURL:    user.photoURL,
      provider:    primaryProvider,
      providers,
      createdAt:   serverTimestamp(),
      lastLogin:   serverTimestamp(),
      role:        'analyst',
    }
    await setDoc(ref, profile)
    return profile
  } else {
    // Existing user — update lastLogin + providers list
    await updateDoc(ref, {
      lastLogin: serverTimestamp(),
      providers,
      photoURL:    user.photoURL ?? snap.data().photoURL,
      displayName: user.displayName ?? snap.data().displayName,
    })
    return { ...(snap.data() as UserProfile), providers }
  }
}

export async function getUserProfile(uid: string): Promise<UserProfile | null> {
  const snap = await getDoc(doc(db, 'users', uid))
  return snap.exists() ? (snap.data() as UserProfile) : null
}

// ── Auth Actions ──────────────────────────────────────────────────────────────
export async function signUpEmail(email: string, password: string): Promise<User> {
  const cred = await createUserWithEmailAndPassword(auth, email, password)
  await upsertUserProfile(cred.user)
  return cred.user
}

export async function signInEmail(email: string, password: string): Promise<User> {
  const cred = await signInWithEmailAndPassword(auth, email, password)
  await upsertUserProfile(cred.user)
  return cred.user
}

export async function signInGoogle(): Promise<User> {
  const cred = await signInWithPopup(auth, googleProvider)
  await upsertUserProfile(cred.user)
  return cred.user
}

export async function resetPassword(email: string): Promise<void> {
  await sendPasswordResetEmail(auth, email)
}

export async function logOut(): Promise<void> {
  await signOut(auth)
}

// Watch auth state changes
export { onAuthStateChanged }
export type { User }
