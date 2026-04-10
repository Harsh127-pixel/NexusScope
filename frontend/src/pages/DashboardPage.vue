<template>
  <q-page class="q-pa-xl">
    <!-- 1. PAGE HEADER -->
    <header class="q-mb-xl">
      <div class="ns-label q-mb-xs">NEXUSSCOPE / DASHBOARD</div>
      <h1 class="ns-heading-xl q-ma-none">Intelligence Overview</h1>
      <div class="ns-muted text-mono q-mt-sm">{{ currentTime }}</div>
    </header>

    <!-- 2. STATS STRIP -->
    <div class="row q-col-gutter-lg q-mb-xl">
      <div v-for="(stat, key) in displayStats" :key="key" class="col-12 col-sm-6 col-md-3">
        <div class="ns-stat-card">
          <div class="ns-label text-muted">{{ stat.label }}</div>
          <div class="stat-value ns-heading-lg q-mt-xs">
            {{ stat.prefix }}{{ stat.currentValue }}{{ stat.suffix }}
          </div>
        </div>
      </div>
    </div>

    <div class="row q-col-gutter-xl q-mb-xl items-stretch">
      <!-- LEFT COLUMN -->
      <div class="col-12 col-lg-8 column">
        <!-- 3. QUICK LAUNCH -->
        <section class="col column">
          <div class="ns-label q-mb-md">QUICK LAUNCH MODULES</div>
          <div class="ns-module-grid">
            <div 
              v-for="module in modules" 
              :key="module.name" 
              class="ns-module-card clickable"
              @click="navigateToModule(module.name)"
            >
              <div class="row no-wrap items-center full-width">
                <component :is="module.icon" :size="32" class="ns-accent-text q-mr-md shrink-0" />
                <div class="column col min-width-0">
                  <div class="module-name text-white text-weight-medium ellipsis">{{ module.name }}</div>
                  <div class="module-desc ns-muted text-caption ellipsis">{{ module.desc }}</div>
                </div>
              </div>
              <q-badge 
                :color="module.status === 'ACTIVE' ? 'positive' : 'negative'" 
                class="absolute-top-right q-ma-xs ns-label"
                style="font-size: 8px"
              >
                {{ module.status }}
              </q-badge>
            </div>
          </div>
        </section>
      </div>

      <!-- RIGHT COLUMN -->
      <div class="col-12 col-lg-4 column">
        <!-- 5. SYSTEM STATUS -->
        <section class="col column">
          <div class="ns-label q-mb-md">SYSTEM INFRASTRUCTURE</div>
          <q-card flat class="q-pa-lg ns-status-panel col column justify-center">
            <div class="column q-gutter-y-lg">
              <!-- API STATUS -->
              <div class="row items-center justify-between no-wrap full-width">
                <div class="row items-center no-wrap q-mr-sm ellipsis">
                  <Server :size="18" class="ns-muted q-mr-md" />
                  <span class="text-white text-weight-medium ellipsis">API ENGINE</span>
                </div>
                <div class="row items-center no-wrap">
                  <span class="text-mono ns-muted q-mr-sm" style="font-size: 11px">
                    {{ dashboardStore.systemStatus.api.latency }}
                  </span>
                  <q-badge color="positive" rounded class="ns-label">
                    {{ dashboardStore.systemStatus.api.status }}
                  </q-badge>
                </div>
              </div>

              <!-- REDIS STATUS -->
              <div class="row items-center justify-between no-wrap full-width">
                <div class="row items-center no-wrap q-mr-sm ellipsis">
                  <Database :size="18" class="ns-muted q-mr-md" />
                  <span class="text-white text-weight-medium ellipsis">TASK BROKER</span>
                </div>
                <div class="row items-center no-wrap">
                  <span class="text-mono ns-muted q-mr-sm" style="font-size: 11px">
                    {{ dashboardStore.systemStatus.redis.tasks }} QUEUED
                  </span>
                  <q-badge color="positive" rounded class="ns-label">
                    {{ dashboardStore.systemStatus.redis.status }}
                  </q-badge>
                </div>
              </div>

              <!-- FIRESTORE STATUS -->
              <div class="row items-center justify-between no-wrap full-width">
                <div class="row items-center no-wrap q-mr-sm ellipsis">
                  <Cloud :size="18" class="ns-muted q-mr-md" />
                  <span class="text-white text-weight-medium ellipsis">INTELLIGENCE DB</span>
                </div>
                <div class="row items-center no-wrap">
                  <span class="text-mono ns-muted q-mr-sm" style="font-size: 11px">
                    {{ dashboardStore.systemStatus.firestore.throughput }}
                  </span>
                  <q-badge color="positive" rounded class="ns-label">
                    {{ dashboardStore.systemStatus.firestore.status }}
                  </q-badge>
                </div>
              </div>
            </div>

            <div class="q-mt-xl q-pt-lg border-top ns-muted text-caption text-mono text-center">
              LAST SYSTEM PING: JUST NOW
            </div>
          </q-card>
        </section>
      </div>
    </div>

    <!-- 4. RECENT ACTIVITY (Full Width) -->
    <section>
      <div class="row items-center justify-between q-mb-md">
        <div class="ns-label">RECENT ACTIVITY</div>
        <router-link to="/history" class="ns-label ns-accent-text text-decoration-none hover-underline">
          VIEW ALL HISTORY
        </router-link>
      </div>
      <q-table
        :rows="dashboardStore.recentTasks"
        :columns="columns"
        row-key="id"
        flat
        dark
        hide-pagination
        class="ns-table-container"
        @row-click="onRowClick"
      >
        <template v-slot:body-cell-status="props">
          <q-td :props="props">
            <q-badge :class="getStatusClass(props.value)" class="ns-label">
              {{ props.value }}
            </q-badge>
          </q-td>
        </template>
        <template v-slot:no-data>
          <div class="full-width column flex-center q-pa-xl ns-muted">
            <Activity :size="48" class="q-mb-md opacity-2" />
            No tasks yet. Run your first query.
          </div>
        </template>
      </q-table>
    </section>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useDashboardStore } from 'src/stores/dashboardStore'
import { 
  User, 
  Globe, 
  MapPin, 
  FileSearch, 
  Navigation, 
  Code,
  Activity,
  Server,
  Database,
  Cloud
} from 'lucide-vue-next'

const router = useRouter()
const dashboardStore = useDashboardStore()

// 1. LIVE CLOCK
const currentTime = ref(new Date().toLocaleString())
let clockInterval: any = null

onMounted(() => {
  clockInterval = setInterval(() => {
    currentTime.value = new Date().toLocaleString('en-US', {
      weekday: 'short',
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    })
  }, 1000)

  animateStats()
})

onUnmounted(() => {
  if (clockInterval) clearInterval(clockInterval)
})

// 2. STATS ANIMATION
const displayStats = reactive({
  totalQueries: { label: 'TOTAL QUERIES', currentValue: 0, targetValue: dashboardStore.stats.totalQueries, prefix: '' },
  activeTasks: { label: 'ACTIVE TASKS', currentValue: 0, targetValue: dashboardStore.stats.activeTasks, prefix: '' },
  avgResolution: { label: 'AVG. RESOLUTION', currentValue: 0, targetValue: (dashboardStore.stats.avgResolutionMs / 1000), prefix: '', suffix: 's' },
  modulesOnline: { label: 'MODULES ONLINE', currentValue: 0, targetValue: dashboardStore.stats.modulesOnline, prefix: '' }
})

const animateStats = () => {
  const duration = 800
  const frameRate = 60
  const totalFrames = (duration / 1000) * frameRate
  
  Object.keys(displayStats).forEach(key => {
    const k = key as keyof typeof displayStats
    const increment = displayStats[k].targetValue / totalFrames
    let current = 0
    let frame = 0

    const timer = setInterval(() => {
      frame++
      current += increment
      if (frame >= totalFrames) {
        displayStats[k].currentValue = displayStats[k].targetValue
        clearInterval(timer)
      } else {
        displayStats[k].currentValue = Math.floor(current * 10) / 10
      }
    }, 1000 / frameRate)
  })
}

// 3. MODULES CONFIG
const modules = [
  { name: 'Username Recon', desc: 'Cross-platform identity tracking', icon: User, status: 'ACTIVE' },
  { name: 'Domain Analysis', desc: 'DNS, WHOIS, record lookup', icon: Globe, status: 'ACTIVE' },
  { name: 'IP Intelligence', desc: 'Geolocation and WHOIS data', icon: MapPin, status: 'ACTIVE' },
  { name: 'Metadata Extraction', desc: 'EXIF and file metadata', icon: FileSearch, status: 'ACTIVE' },
  { name: 'Geolocation', desc: 'Coordinate and location mapping', icon: Navigation, status: 'ACTIVE' },
  { name: 'Web Scraper', desc: 'Headless browser intelligence', icon: Code, status: 'ACTIVE' }
]

const navigateToModule = (name: string) => {
  router.push(`/search?module=${encodeURIComponent(name.toLowerCase())}`)
}

// 4. ACTIVITY TABLE CONFIG
const columns = [
  { name: 'id', label: 'TASK ID', field: 'id', align: 'left', classes: 'text-mono ns-muted' },
  { name: 'module', label: 'MODULE', field: 'module', align: 'left', classes: 'text-weight-medium' },
  { name: 'target', label: 'TARGET', field: 'target', align: 'left' },
  { name: 'status', label: 'STATUS', field: 'status', align: 'left' },
  { name: 'duration', label: 'DURATION', field: 'duration', align: 'right', classes: 'text-mono ns-muted' },
  { name: 'timestamp', label: 'TIMESTAMP', field: 'timestamp', align: 'right' }
]

const getStatusClass = (status: string) => {
  switch (status) {
    case 'QUEUED': return 'bg-amber text-black'
    case 'PROCESSING': return 'bg-blue text-white animate-pulse'
    case 'COMPLETED': return 'bg-positive text-black'
    case 'FAILED': return 'bg-negative text-white'
    default: return ''
  }
}

const onRowClick = (evt: any, row: any) => {
  router.push(`/results/${row.id}`)
}
</script>

<style lang="css" scoped>
/* STATS STRIP */
.ns-stat-card {
  background: var(--ns-bg-surface);
  padding: var(--ns-space-5);
  border-radius: var(--ns-radius-md);
  transition: var(--ns-transition);
}

.ns-stat-card:hover {
  background: var(--ns-bg-elevated);
}

.stat-value {
  color: var(--ns-accent);
}

/* MODULE GRID */
.ns-module-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--ns-space-4);
}

@media (max-width: 1439px) { /* Under lg breakpoint */
  .ns-module-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 1023px) { /* Under md breakpoint */
  .ns-module-grid { grid-template-columns: 1fr; }
}

.ns-module-card {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  padding: var(--ns-space-5);
  border-radius: var(--ns-radius-md);
  position: relative;
  transition: all 0.2s ease;
}

.ns-module-card:hover {
  border-color: var(--ns-accent);
  box-shadow: var(--ns-accent-glow);
  transform: translateY(-2px);
}

.ns-accent-text {
  color: var(--ns-accent);
}

/* SYSTEM STATUS */
.ns-status-panel {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  border-radius: var(--ns-radius-lg);
}

.border-top {
  border-top: 1px solid var(--ns-border);
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.hover-underline:hover {
  text-decoration: underline;
}

.clickable {
  cursor: pointer;
}

.shrink-0 {
  flex-shrink: 0 !important;
}

.min-width-0 {
  min-width: 0 !important;
}
</style>
