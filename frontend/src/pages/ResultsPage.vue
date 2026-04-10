<template>
  <q-page class="q-pa-xl">
    <!-- TASK HEADER -->
    <div class="row items-center justify-between q-mb-xl">
      <div class="column">
        <q-breadcrumbs class="ns-label q-mb-sm" active-color="primary">
          <q-breadcrumbs-el label="DASHBOARD" to="/" />
          <q-breadcrumbs-el label="SEARCH" to="/search" />
          <q-breadcrumbs-el label="RESULTS" />
        </q-breadcrumbs>
        
        <div class="row items-center q-gutter-x-md">
          <div 
            class="ns-heading-md text-white cursor-pointer hover-accent" 
            @click="copyTaskId"
          >
            {{ taskId }}
            <q-tooltip>CLICK TO COPY TASK ID</q-tooltip>
          </div>
          <q-badge :color="getModuleColor" class="ns-label q-pa-sm">
            {{ resultsStore.currentTask?.type || 'MODULE_UNKNOWN' }}
          </q-badge>
          <div class="row items-center ns-muted text-mono text-caption">
            <Target :size="14" class="q-mr-xs" />
            {{ resultsStore.currentTask?.target || 'TARGETING...' }}
          </div>
          <q-badge 
            :color="getStatusColor" 
            :class="{ 'animate-pulse': resultsStore.currentTask?.status === 'processing' }"
            class="ns-label"
          >
            {{ resultsStore.currentTask?.status?.toUpperCase() || 'INITIALIZING' }}
          </q-badge>
        </div>
      </div>

      <div class="row q-gutter-x-sm" v-if="resultsStore.currentTask?.status === 'completed'">
        <q-btn flat class="ns-btn-secondary" icon="download" label="EXPORT JSON" @click="exportJson" />
        <q-btn flat class="ns-btn-secondary" icon="content_copy" label="COPY RAW" @click="copyRaw" />
        <q-btn color="primary" icon="add" label="NEW SEARCH" to="/search" />
      </div>
    </div>

    <!-- POLLING / LOADING STATE -->
    <div v-if="resultsStore.isPolling" class="column flex-center q-py-xl">
      <q-linear-progress indeterminate color="primary" class="q-mb-xl" />
      
      <q-card flat class="ns-polling-card q-pa-xl">
        <div class="text-center">
          <component 
            :is="getActiveModuleIcon" 
            :size="64" 
            class="ns-accent-text q-mb-lg animate-bounce" 
          />
          <h2 class="ns-heading-md text-white q-mb-md">Analyzing Target Environment...</h2>
        </div>

        <div class="ns-terminal-output q-mt-xl bg-black q-pa-md rounded-borders border-ns">
          <div 
            v-for="(log, index) in resultsStore.logs" 
            :key="index" 
            class="text-mono text-caption q-mb-xs"
          >
            {{ log }}
          </div>
          <div class="text-blue animate-pulse q-mt-sm">[_] Awaiting synchronization...</div>
        </div>
      </q-card>
    </div>

    <!-- RESULTS DISPLAY -->
    <div v-if="resultsStore.currentTask?.status === 'completed'" class="ns-results-container">
      <q-tabs
        v-model="activeTab"
        dense
        class="ns-tabs text-grey"
        active-color="primary"
        indicator-color="primary"
        align="left"
        narrow-indicator
      >
        <q-tab name="summary" label="SUMMARY" class="ns-label" />
        <q-tab name="raw" label="RAW DATA" class="ns-label" />
        <q-tab name="table" label="TABLE VIEW" class="ns-label" />
        <q-tab v-if="hasMapData" name="map" label="GEOSPATIAL" class="ns-label" />
        <q-tab name="related" label="RELATED" class="ns-label" />
      </q-tabs>

      <q-separator dark class="q-mb-lg opacity-1" />

      <q-tab-panels v-model="activeTab" animated background-color="transparent" transition-duration="150" class="bg-transparent">
        <!-- SUMMARY TAB -->
        <q-tab-panel name="summary" class="q-pa-none">
          <div class="row q-col-gutter-lg">
            <div v-for="(val, key) in summaryData" :key="key" class="col-12 col-sm-6 col-md-4">
              <q-card flat class="ns-summary-cell q-pa-md">
                <div class="ns-label text-muted q-mb-xs">{{ formatKey(key) }}</div>
                <div class="text-mono text-weight-bold text-white ellipsis">{{ val }}</div>
              </q-card>
            </div>
          </div>
          
          <div class="q-mt-xl" v-if="resultsStore.currentTask.results?.risk_score">
            <div class="row items-center justify-between q-mb-sm">
              <span class="ns-label">CONFIDENCE / RISK ASSESSMENT</span>
              <span class="text-mono text-primary">{{ resultsStore.currentTask.results.risk_score }}%</span>
            </div>
            <q-linear-progress 
              :value="resultsStore.currentTask.results.risk_score / 100" 
              color="primary" 
              size="12px" 
              class="rounded-borders ns-progress-bg"
            />
          </div>
        </q-tab-panel>

        <!-- RAW DATA TAB -->
        <q-tab-panel name="raw" class="q-pa-none">
          <div class="ns-json-header row items-center q-mb-md">
            <q-input 
              v-model="jsonFilter" 
              dense 
              filled 
              placeholder="FILTER NODES..." 
              class="col text-mono" 
              dark
            />
          </div>
          <div class="ns-json-tree bg-surface q-pa-md rounded-borders border-ns">
            <vue-json-pretty
              :data="resultsStore.currentTask.results"
              :deep="3"
              showLine
              showIcon
              @click="onJsonNodeClick"
              theme="dark"
            />
          </div>
        </q-tab-panel>

        <!-- TABLE VIEW TAB -->
        <q-tab-panel name="table" class="q-pa-none">
          <q-table
            :rows="tableData"
            :columns="tableColumns"
            flat
            dark
            bordered
            class="ns-results-table"
          />
        </q-tab-panel>

        <!-- MAP TAB -->
        <q-tab-panel name="map" class="q-pa-none">
          <div id="result-map" class="ns-map-container rounded-borders border-ns"></div>
        </q-tab-panel>

        <!-- RELATED TAB -->
        <q-tab-panel name="related" class="q-pa-none">
          <div class="ns-label q-mb-md">SUGGESTED FOLLOW-UP QUERIES</div>
          <div class="row q-gutter-sm">
            <q-chip 
              v-for="query in relatedQueries" 
              :key="query" 
              clickable 
              @click="dispatchSearch(query)"
              color="bg-surface"
              text-color="primary"
              class="ns-related-chip"
              icon="radar"
            >
              {{ query }}
            </q-chip>
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </div>

    <!-- FAILED STATE -->
    <div v-if="resultsStore.currentTask?.status === 'failed'" class="column flex-center q-py-xl">
      <q-banner class="bg-negative text-white rounded-borders q-pa-lg">
        <template v-slot:avatar>
          <q-icon name="warning" size="md" />
        </template>
        <div class="text-h6">INVESTIGATION TERMINATED PREMATURELY</div>
        <div class="text-mono q-mt-sm">{{ resultsStore.error || 'ERROR_UNKNOWN_TERMINATION' }}</div>
      </q-banner>
      <div class="row q-gutter-x-md q-mt-xl">
        <q-btn color="white" text-color="black" label="RETRY" @click="startPolling" />
        <q-btn color="primary" label="NEW SEARCH" to="/search" />
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useResultsStore } from 'src/stores/resultsStore'
import { useQuasar, copyToClipboard } from 'quasar'
import { 
  Target, User, Globe, MapPin, FileSearch, 
  Navigation, Code, Layers, Search 
} from 'lucide-vue-next'
import VueJsonPretty from 'vue-json-pretty'
import 'vue-json-pretty/lib/styles.css'

const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const resultsStore = useResultsStore()

const taskId = computed(() => route.params.taskId as string)
const activeTab = ref((route.hash.replace('#', '') as string) || 'summary')
const jsonFilter = ref('')
let pollInterval: any = null

// Tab persistence
watch(activeTab, (val) => {
  window.location.hash = val
  if (val === 'map') initMap()
})

onMounted(() => {
  startPolling()
})

onUnmounted(() => {
  clearInterval(pollInterval)
  resultsStore.reset()
})

const startPolling = () => {
  resultsStore.startPolling(taskId.value)
}

watch(() => resultsStore.taskData?.status, (newStatus) => {
  if (newStatus === 'completed') {
    if (activeTab.value === 'map') nextTick(() => initMap())
  }
})

// Visualization Logic
const summaryData = computed(() => {
  if (!resultsStore.currentTask?.results) return {}
  const res = resultsStore.currentTask.results
  return {
    'PRIMARY_HOST': res.domain,
    'RESOLVED_IP': res.ip_address,
    'PRIMARY_MX': res.records?.MX,
    'ASN': 'AS15169',
    'CITY': res.location?.city,
    'COUNTRY': res.location?.country
  }
})

const hasMapData = computed(() => !!resultsStore.currentTask?.results?.location)

const tableData = computed(() => [resultsStore.currentTask?.results])
const tableColumns = [
  { name: 'field', label: 'FIELD', field: (row: any) => Object.keys(row)[0], align: 'left', classes: 'ns-label' },
  { name: 'value', label: 'VALUE', field: (row: any) => Object.values(row)[0], align: 'left' }
]

// Map Initialization
let map: any = null
const initMap = async () => {
  if (!hasMapData.value) return
  
  // Dynamic Leaflet Import
  const L = (await import('leaflet')).default
  import ('leaflet/dist/leaflet.css')

  nextTick(() => {
    const loc = resultsStore.currentTask.results.location
    if (map) return
    
    map = L.map('result-map').setView([loc.lat, loc.lng], 12)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; CartoDB'
    }).addTo(map)
    
    L.marker([loc.lat, loc.lng]).addTo(map)
      .bindPopup(`<b>${loc.city}, ${loc.country}</b><br>${resultsStore.currentTask.target}`)
      .openPopup()
  })
}

// Helpers
const getStatusColor = computed(() => {
  const s = resultsStore.currentTask?.status
  if (s === 'completed') return 'positive'
  if (s === 'processing') return 'blue'
  if (s === 'failed') return 'negative'
  return 'grey'
})

const getModuleColor = computed(() => {
  const t = resultsStore.currentTask?.type
  if (t === 'dns') return 'indigo-7'
  return 'primary'
})

const getActiveModuleIcon = computed(() => {
  const t = resultsStore.currentTask?.type
  if (t === 'dns') return Globe
  if (t === 'social') return User
  return Layers
})

const formatKey = (key: string) => key.replace(/_/g, ' ')

const copyTaskId = () => {
  copyToClipboard(taskId.value).then(() => {
    $q.notify({ message: 'Task ID copied to clipboard', color: 'positive', position: 'bottom' })
  })
}

const exportJson = () => {
  const data = JSON.stringify(resultsStore.currentTask, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `nexus_task_${taskId.value}.json`
  a.click()
}

const copyRaw = () => {
  copyToClipboard(JSON.stringify(resultsStore.currentTask, null, 2)).then(() => {
    $q.notify({ message: 'Raw data copied', color: 'primary' })
  })
}

const relatedQueries = ['Scan Subdomains', 'Reverse IP Lookup', 'Analyze ASN AS15169']
const dispatchSearch = (query: string) => {
  router.push(`/search?target=${query}`)
}

const onJsonNodeClick = (path: string) => {
  console.log('JSON Path selected:', path)
}
</script>

<style scoped>
.ns-polling-card {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  width: 100%;
  max-width: 600px;
}

.ns-terminal-output {
  height: 200px;
  overflow-y: auto;
  border: 1px solid var(--ns-border);
}

.ns-summary-cell {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  transition: var(--ns-transition);
}

.ns-summary-cell:hover {
  background: var(--ns-bg-elevated);
  border-color: var(--ns-accent);
}

.ns-map-container {
  height: 400px;
  background: var(--ns-bg-surface);
}

.ns-json-tree {
  max-height: 600px;
  overflow: auto;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.animate-bounce {
  animation: bounce 1s infinite;
}

@keyframes bounce {
  0%, 100% { transform: translateY(-10%); animation-timing-function: cubic-bezier(0.8, 1, 1); }
  50% { transform: translateY(0); animation-timing-function: cubic-bezier(0, 0, 0.2, 1); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.ns-accent-text { color: var(--ns-accent); }
.border-ns { border: 1px solid var(--ns-border); }
.ns-progress-bg { background-color: var(--ns-bg-surface); }
.hover-accent:hover { color: var(--ns-accent); transition: color 0.2s; }

/* JSON Tree Styles Override */
:deep(.vjs-tree) { border: none !important; }
:deep(.vjs-value__string) { color: var(--ns-accent); }
:deep(.vjs-key) { color: #fff; }
</style>
