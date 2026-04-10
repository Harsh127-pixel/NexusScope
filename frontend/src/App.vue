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

@media print {
  html, body, #q-app {
    background: #ffffff !important;
    color: #111111 !important;
    height: auto !important;
    overflow: visible !important;
  }

  body {
    font-family: 'IBM Plex Sans', Arial, sans-serif !important;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  .q-header,
  .q-drawer,
  .q-footer,
  .ns-header,
  .ns-sidebar,
  .ns-global-search,
  .q-btn,
  .q-pagination,
  .q-tab,
  .q-tabs,
  .q-tooltip {
    display: none !important;
  }

  .ns-print-only-domain-report {
    display: block !important;
  }

  .ns-results-container > :not(.ns-print-only-domain-report) {
    display: none !important;
  }

  .q-page-container,
  .q-page,
  .q-layout,
  .q-layout__section,
  .q-layout__shadow,
  .q-layout__shadow--left,
  .q-layout__shadow--right {
    position: static !important;
    min-height: auto !important;
    height: auto !important;
    width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
    background: #ffffff !important;
    box-shadow: none !important;
  }

  .ns-content-container {
    padding-top: 0 !important;
  }

  .ns-page-title,
  .ns-heading-xl,
  .ns-heading-lg,
  .ns-heading-md,
  .ns-heading-sm,
  .ns-label,
  .text-mono,
  .ns-muted {
    color: #111111 !important;
  }

  .q-card,
  .ns-search-container,
  .ns-terminal-preview,
  .ns-polling-card,
  .ns-summary-cell,
  .ns-stat-card,
  .ns-status-panel,
  .ns-table-container,
  .ns-json-tree,
  .ns-map-container,
  .ns-report-card,
  .ns-report-block {
    background: #ffffff !important;
    color: #111111 !important;
    border: 1px solid #d0d7de !important;
    box-shadow: none !important;
  }

  .q-badge {
    display: inline-flex !important;
    align-items: center;
    background: transparent !important;
    color: #111111 !important;
    border: 1px solid #d0d7de !important;
    padding: 2px 8px !important;
    min-height: 0 !important;
  }

  .ns-terminal-preview,
  .ns-polling-card,
  .ns-table-container,
  .ns-json-tree,
  .ns-report-card,
  .ns-report-block {
    break-inside: avoid;
    page-break-inside: avoid;
  }

  .row,
  .column {
    break-inside: avoid;
  }

  a[href]:after {
    content: "";
  }
}
</style>
