<template>
  <router-view v-slot="{ Component }">
    <transition name="page-fade" mode="out-in">
      <component :is="Component" />
    </transition>
  </router-view>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useQuasar, Notify } from 'quasar'
import { useAppStore } from 'src/stores/appStore'

const $q = useQuasar()
const appStore = useAppStore()

// --- GLOBAL NOTIFY DEFAULTS ---
Notify.setDefaults({
  position: 'bottom-right',
  timeout: 3000,
  textColor: 'white',
  actions: [{ icon: 'close', color: 'white', round: true, flat: true }]
})

// --- GLOBAL API HEALTH MONITORING ---
let healthCheckInterval: any = null

onMounted(() => {
  appStore.checkApiHealth()
  
  // Tactical heartbeat every 30 seconds
  healthCheckInterval = setInterval(() => {
    appStore.checkApiHealth()
  }, 30000)
})

onUnmounted(() => {
  if (healthCheckInterval) clearInterval(healthCheckInterval)
})
</script>

<style>
/* App-level global styles to ensure animations are available */
@import './css/animations.css';
</style>
