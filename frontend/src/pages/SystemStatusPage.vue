<template>
  <q-page class="q-pa-md ns-status-page">
    <!-- Header Hero -->
    <div class="ns-status-hero q-mb-lg row items-center justify-between q-pa-xl">
      <div class="column">
        <h1 class="ns-heading-lg q-mb-xs">CORE SYSTEMS STATUS</h1>
        <p class="ns-text-muted q-mb-none">Real-time health monitoring of theater modules and aggregation nodes.</p>
      </div>
      <div class="column items-end">
        <div :class="['ns-global-status', appStore.isApiConnected ? 'is-nominal' : 'is-critical']">
          <Activity :size="24" class="q-mr-sm" />
          {{ appStore.isApiConnected ? 'SYSTEM NOMINAL' : 'SYSTEM OFFLINE' }}
        </div>
        <div class="ns-timestamp-sm q-mt-sm">LAST SYNC: {{ lastSyncTime }}</div>
      </div>
    </div>

    <div class="row q-col-gutter-lg">
      <!-- Theater Modules Grid -->
      <div class="col-12 col-md-8">
        <div class="row q-col-gutter-md">
          <div v-for="theater in theaters" :key="theater.id" class="col-12 col-sm-6">
            <ns-card :title="theater.name">
              <template #header-actions>
                <q-badge :color="theater.status === 'online' ? 'positive' : 'negative'" rounded />
              </template>
              
              <div class="row items-center justify-between q-mb-md">
                <span class="ns-label-sm">CONNECTIVITY</span>
                <span :class="['ns-status-text', theater.status]">{{ theater.status.toUpperCase() }}</span>
              </div>

              <div class="ns-progress-mini q-mb-lg">
                <div class="ns-progress-bar" :style="{ width: theater.uptime + '%', background: theater.status === 'online' ? 'var(--ns-accent)' : '#ef4444' }" />
              </div>

              <div class="row q-col-gutter-sm">
                <div v-for="mod in theater.modules" :key="mod" class="col-auto">
                  <q-chip dense dark size="10px" class="ns-module-chip" :label="mod.toUpperCase()" />
                </div>
              </div>
            </ns-card>
          </div>
        </div>

        <ns-card title="NETWORK LATENCY (TACTICAL NODES)" class="q-mt-lg">
          <div class="ns-latency-chart">
            <div v-for="i in 20" :key="i" class="ns-latency-bar" :style="{ height: Math.random() * 60 + 20 + '%', opacity: 0.3 + (i / 20) * 0.7 }" />
          </div>
          <div class="row justify-between q-mt-md">
            <div class="column">
              <span class="ns-label-sm">PRIMARY GATEWAY</span>
              <span class="ns-value-md">14ms</span>
            </div>
            <div class="column items-end">
              <span class="ns-label-sm">TOR RELAY</span>
              <span class="ns-value-md">1.2s</span>
            </div>
          </div>
        </ns-card>
      </div>

      <!-- Infrastructure Logs -->
      <div class="col-12 col-md-4">
        <ns-card title="SYSTEM LOGS" class="full-height border-none">
          <div class="ns-status-logs text-mono">
            <div v-for="(log, i) in logs" :key="i" class="ns-log-entry">
              <span class="ns-log-time">{{ log.time }}</span>
              <span :class="['ns-log-msg', log.type]">{{ log.msg }}</span>
            </div>
          </div>
          
          <q-btn
            flat
            no-caps
            class="full-width q-mt-md ns-text-muted"
            icon="refresh"
            label="FORCE SYSTEM AUDIT"
            :loading="loading"
            @click="refresh"
          />
        </ns-card>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Activity } from 'lucide-vue-next'
import { useAppStore } from 'src/stores/appStore'
import NsCard from 'components/NsCard.vue'

const appStore = useAppStore()
const loading = ref(false)
const lastSyncTime = ref(new Date().toLocaleTimeString())

const theaters = ref([
  { id: 1, name: 'THEATER I: DARK WEB', status: 'online', uptime: 98.4, modules: ['Onion Crawler', 'Tor Proxy'] },
  { id: 2, name: 'THEATER II: RECON', status: 'online', uptime: 99.9, modules: ['IP Intel', 'DNS', 'Phone'] },
  { id: 3, name: 'THEATER III: IDENTITY', status: 'online', uptime: 92.1, modules: ['Gravatar', 'Breach Search'] },
  { id: 4, name: 'THEATER IV: DEEP SEARCH', status: appStore.isApiConnected ? 'online' : 'offline', uptime: 99.5, modules: ['LeakOSINT', 'Billing API'] }
])

const logs = ref([
  { time: '10:04:12', type: 'info', msg: 'Core API connection established.' },
  { time: '10:04:13', type: 'info', msg: 'PostgreSQL pool nominal (12 connections).' },
  { time: '10:05:01', type: 'warn', msg: 'Theater I relay latency high: 1.4s' },
  { time: '10:05:45', type: 'info', msg: 'Firebase Auth token verified.' },
  { time: '10:08:22', type: 'info', msg: 'LeakOSINT heartbeat received.' },
  { time: '10:10:05', type: 'info', msg: 'Background cleanup task complete.' }
])

const refresh = async () => {
  loading.value = true
  await appStore.checkApiHealth()
  lastSyncTime.value = new Date().toLocaleTimeString()
  setTimeout(() => { loading.value = false }, 1000)
}

onMounted(() => {
  appStore.checkApiHealth()
  const interval = setInterval(() => {
    lastSyncTime.value = new Date().toLocaleTimeString()
  }, 30000)
})
</script>

<style scoped>
.ns-status-hero {
  background: linear-gradient(90deg, rgba(0,212,255,0.05) 0%, transparent 100%);
  border-radius: 16px;
  border: 1px solid var(--ns-border);
}

.ns-global-status {
  display: flex;
  align-items: center;
  font-family: var(--ns-font-mono);
  font-weight: 700;
  padding: 8px 16px;
  border-radius: 99px;
  font-size: 14px;
}

.ns-global-status.is-nominal {
  background: rgba(34,197,94,0.1);
  color: #22c55e;
}

.ns-global-status.is-critical {
  background: rgba(239,68,68,0.1);
  color: #ef4444;
}

.ns-status-text.online { color: var(--ns-accent); }
.ns-status-text.offline { color: #ef4444; }

.ns-module-chip {
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--ns-border);
  font-family: var(--ns-font-mono);
  color: var(--ns-text-muted);
}

.ns-progress-mini {
  height: 4px;
  background: rgba(255,255,255,0.08);
  border-radius: 99px;
}

.ns-progress-bar {
  height: 100%;
  border-radius: 99px;
  transition: width 0.3s ease;
}

.ns-latency-chart {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 80px;
  padding-bottom: 2px;
  border-bottom: 1px solid var(--ns-border);
}

.ns-latency-bar {
  flex: 1;
  background: var(--ns-accent);
  border-radius: 2px 2px 0 0;
}

.ns-status-logs {
  font-size: 11px;
  height: 400px;
  overflow-y: auto;
}

.ns-log-entry {
  padding: 4px 0;
  border-bottom: 1px solid rgba(255,255,255,0.03);
}

.ns-log-time {
  color: var(--ns-text-muted);
  margin-right: 12px;
}

.ns-log-msg.info { color: var(--ns-text-secondary); }
.ns-log-msg.warn { color: #f59e0b; }
.ns-log-msg.error { color: #ef4444; }
</style>
