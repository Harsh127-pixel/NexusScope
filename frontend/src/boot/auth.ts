// src/boot/auth.ts
// Quasar boot — initialise Firebase auth state watcher before app mounts.

import { boot } from 'quasar/wrappers'
import { useAuthStore } from 'src/stores/authStore'

export default boot(({ app }) => {
  // Store must be initialised after Pinia is available
  const authStore = useAuthStore()
  authStore.init()
})
