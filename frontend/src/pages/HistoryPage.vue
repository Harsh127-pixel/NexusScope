<template>
  <q-page :class="$q.screen.gt.sm ? 'q-pa-xl' : 'q-pa-md'">
    <!-- TOP BAR -->
    <div class="row items-start justify-between q-mb-lg q-gutter-y-md">
      <div class="row items-center">
        <h1 class="ns-heading-lg text-white q-ma-none q-mr-md">Investigation History</h1>
        <q-badge color="accent-dim" text-color="primary" class="ns-label q-pa-sm">
          {{ filteredTasks.length }} RECORDS
        </q-badge>
      </div>

      <div class="row items-center q-gutter-sm flex-wrap">
        <!-- Global Search -->
        <q-input 
          v-model="filters.search" 
          dense 
          filled 
          borderless
          placeholder="SEARCH TARGET OR ID..." 
          class="ns-history-search text-mono"
          dark
        >
          <template v-slot:prepend>
            <Search :size="16" class="ns-muted" />
          </template>
        </q-input>

        <!-- Module Filter -->
        <q-select
          v-model="filters.module"
          :options="moduleOptions"
          multiple
          dense
          filled
          label="MODULES"
          class="ns-filter-select"
          dark
          emit-value
          map-options
          counter
        >
          <template v-slot:selected-item="scope">
            <span v-if="scope.index === 0" class="ns-label text-caption">SELECTED</span>
          </template>
        </q-select>

        <!-- Status Filter -->
        <q-select
          v-model="filters.status"
          :options="statusOptions"
          dense
          filled
          label="STATUS"
          class="ns-filter-select"
          dark
        />

        <!-- Date Range -->
        <q-btn flat dense class="ns-btn-secondary q-px-md" icon="event">
          <span class="q-ml-sm ns-label" v-if="$q.screen.gt.xs">RANGE</span>
          <q-popup-proxy cover transition-show="scale" transition-hide="scale">
            <q-date v-model="filters.dateRange" range dark color="primary">
              <div class="row items-center justify-end q-gutter-sm">
                <q-btn label="Cancel" color="primary" flat v-close-popup />
                <q-btn label="OK" color="primary" flat v-close-popup />
              </div>
            </q-date>
          </q-popup-proxy>
        </q-btn>

        <q-btn 
          v-if="hasFilters"
          flat 
          round 
          color="negative" 
          @click="clearFilters"
          icon="filter_list_off"
        >
          <q-tooltip>CLEAR FILTERS</q-tooltip>
        </q-btn>
      </div>
    </div>

    <!-- MAIN TABLE -->
    <div class="ns-history-table-container">
      <q-table
        v-model:selected="selectedRows"
        :rows="filteredTasks"
        :columns="columns"
        row-key="id"
        selection="multiple"
        flat
        dark
        bordered
        :pagination="pagination"
        class="ns-history-table"
        :no-data-label="emptyStateHeading"
      >
        <!-- Task ID Column -->
        <template v-slot:body-cell-id="props">
          <q-td :props="props" class="text-mono color-primary">
            {{ props.value.substring(0, 8) }}...
            <q-tooltip>{{ props.value }}</q-tooltip>
          </q-td>
        </template>

        <!-- Module Column -->
        <template v-slot:body-cell-module="props">
          <q-td :props="props">
            <div class="row items-center no-wrap">
              <component :is="getModuleIcon(props.value)" :size="16" :class="getModuleTextClass(props.value)" class="q-mr-sm" />
              <span class="text-weight-medium">{{ props.value.toUpperCase() }}</span>
            </div>
          </q-td>
        </template>

        <!-- Target Column -->
        <template v-slot:body-cell-target="props">
          <q-td :props="props" class="ellipsis overflow-hidden" style="max-width: 200px">
            {{ props.value }}
            <q-tooltip>{{ props.value }}</q-tooltip>
          </q-td>
        </template>

        <!-- Status Column -->
        <template v-slot:body-cell-status="props">
          <q-td :props="props">
            <q-badge 
              :color="getStatusColor(props.value)" 
              :class="{ 'animate-pulse': props.value === 'processing' }"
              class="ns-label q-pa-xs"
            >
              {{ props.value.toUpperCase() }}
            </q-badge>
          </q-td>
        </template>

        <!-- Started Column -->
        <template v-slot:body-cell-started="props">
          <q-td :props="props" class="ns-muted">
            {{ formatRelative(props.value) }}
            <q-tooltip>{{ new Date(props.value).toLocaleString() }}</q-tooltip>
          </q-td>
        </template>

        <!-- Duration Column -->
        <template v-slot:body-cell-duration="props">
          <q-td :props="props" class="text-mono ns-muted">
            {{ props.value }}
          </q-td>
        </template>

        <!-- Actions Column -->
        <template v-slot:body-cell-actions="props">
          <q-td :props="props" class="q-gutter-x-xs">
            <q-btn flat round dense color="primary" icon="visibility" @click="viewResults(props.row.id)">
              <q-tooltip>VIEW RESULTS</q-tooltip>
            </q-btn>
            <q-btn flat round dense color="accent-text" icon="refresh" @click="reRun(props.row)">
              <q-tooltip>RE-RUN INVESTIGATION</q-tooltip>
            </q-btn>
            <q-btn flat round dense color="negative" icon="delete" @click="confirmDelete(props.row.id)">
              <q-tooltip>REMOVE RECORD</q-tooltip>
            </q-btn>
          </q-td>
        </template>

        <!-- Empty State -->
        <template v-slot:no-data>
          <div class="full-width column flex-center q-pa-xl">
            <div class="icon-container opacity-2 q-mb-md">
              <ClipboardList :size="64" />
            </div>
            <div class="text-h6 text-white">{{ emptyStateHeading }}</div>
            <div class="ns-muted q-mb-lg">{{ emptyStateSub }}</div>
            <q-btn 
              v-if="hasFilters" 
              color="primary" 
              label="CLEAR ALL FILTERS" 
              @click="clearFilters" 
            />
            <q-btn 
              v-else 
              color="primary" 
              label="INITIATE NEW QUERY" 
              to="/search" 
            />
          </div>
        </template>
      </q-table>
    </div>

    <!-- BULK ACTIONS BAR -->
    <transition name="slide-fade">
      <div v-if="selectedRows.length > 0" class="ns-bulk-bar fixed-bottom row items-center justify-between q-pa-md shadow-24">
        <div class="row items-center">
          <q-btn flat round icon="close" color="white" @click="selectedRows = []" class="q-mr-sm" />
          <span class="ns-label text-weight-bold text-white">
            {{ selectedRows.length }} INVESTIGATIONS SELECTED
          </span>
        </div>
        <div class="row q-gutter-x-sm">
          <q-btn color="white" text-color="black" icon="download" label="EXPORT JSON" @click="exportSelected" />
          <q-btn color="negative" icon="delete_sweep" label="DELETE SELECTED" @click="confirmDeleteBulk" />
        </div>
      </div>
    </transition>
  </q-page>
</template>


<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import { useHistoryStore } from 'src/stores/historyStore'
import { storeToRefs } from 'pinia'
import { 
  Search, User, Globe, MapPin, FileSearch, 
  Navigation, Code, Activity, ClipboardList, 
  RotateCcw, Trash2, Eye, Database 
} from 'lucide-vue-next'

const $q = useQuasar()
const router = useRouter()
const historyStore = useHistoryStore()
const { filters, filteredTasks } = storeToRefs(historyStore)

const selectedRows = ref([])
const pagination = ref({
  sortBy: 'started',
  descending: true,
  page: 1,
  rowsPerPage: 25
})

const moduleOptions = [
  { label: 'ALL MODULES', value: 'All' },
  { label: 'DOMAIN', value: 'domain' },
  { label: 'IP', value: 'ip' },
  { label: 'USERNAME', value: 'username' },
  { label: 'EMAIL', value: 'email' },
  { label: 'PHONE', value: 'phone' },
  { label: 'METADATA', value: 'metadata' },
  { label: 'SCRAPER', value: 'scraper' },
  { label: 'DARK WEB', value: 'darkweb' },
  { label: 'DEEP SEARCH', value: 'deepsearch' }
]

const statusOptions = ['All', 'Completed', 'Failed', 'Processing', 'Queued']

const columns = [
  { name: 'task_id', label: 'TASK ID', field: 'task_id', align: 'left' as const, sortable: true },
  { name: 'module', label: 'MODULE', field: 'module', align: 'left' as const, sortable: true },
  { name: 'target', label: 'TARGET', field: 'target', align: 'left' as const, sortable: true },
  { name: 'status', label: 'STATUS', field: 'status', align: 'left' as const, sortable: true },
  { name: 'started', label: 'STARTED', field: 'created_at', align: 'left' as const, sortable: true },
  { name: 'duration', label: 'DURATION', field: 'duration_ms', align: 'right' as const },
  { name: 'actions', label: 'ACTIONS', field: 'task_id', align: 'right' as const }
]

onMounted(() => {
  historyStore.fetchHistory()
})

watch(() => historyStore.filters, () => {
  historyStore.fetchHistory()
}, { deep: true })

const hasFilters = computed(() => {
  return historyStore.filters.search || historyStore.filters.module !== 'All' || historyStore.filters.status !== 'All'
})

const clearFilters = () => {
  historyStore.filters = { search: '', module: 'All', status: 'All', dateRange: null }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'positive'
    case 'failed': return 'negative'
    case 'processing': return 'blue'
    case 'queued': return 'amber'
    default: return 'grey'
  }
}

const getModuleIcon = (module: string) => {
  switch (module) {
    case 'domain': return Globe
    case 'username': return User
    case 'ip': return MapPin
    case 'metadata': return FileSearch
    case 'scraper': return Code
    case 'darkweb': return Eye
    case 'deepsearch': return Database
    default: return Activity
  }
}

const getModuleTextClass = (module: string) => {
  switch (module) {
    case 'domain': return 'text-indigo-4'
    case 'username': return 'text-pink-4'
    case 'ip': return 'text-amber-4'
    case 'metadata': return 'text-cyan-4'
    case 'scraper': return 'text-green-4'
    case 'darkweb': return 'text-purple-4'
    case 'deepsearch': return 'text-primary'
    default: return 'text-primary'
  }
}

const formatRelative = (timestamp: string) => {
  if (!timestamp) return '...'
  const diff = Date.now() - new Date(timestamp).getTime()
  if (diff < 60000) return 'Just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} min ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} hours ago`
  return new Date(timestamp).toLocaleDateString()
}

const formatDuration = (ms: number | null) => {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

// Actions
const viewResults = (id: string) => router.push(`/results/${id}`)

const reRun = (task: any) => {
  $q.notify({ message: `Re-dispatching investigation for ${task.target}...`, color: 'primary' })
  router.push(`/search?module=${task.module}&target=${task.target}`)
}

const confirmDelete = (id: string) => {
  $q.dialog({
    title: 'CONFIRM DELETION',
    message: 'Permanently remove this evidence record?',
    dark: true,
    ok: { label: 'DELETE', color: 'negative', flat: true },
    cancel: { label: 'CANCEL', flat: true }
  }).onOk(() => {
    historyStore.deleteTask(id)
    $q.notify({ message: 'Record deleted', color: 'negative', icon: 'delete', position: 'top' })
  })
}

const confirmDeleteBulk = () => {
  const ids = selectedRows.value.map((r: any) => r.task_id)
  $q.dialog({
    title: 'DELETE SELECTION',
    message: `Purge ${ids.length} records?`,
    dark: true,
    ok: { label: 'PURGE', color: 'negative', flat: true },
    cancel: { label: 'CANCEL', flat: true }
  }).onOk(() => {
    historyStore.deleteMany(ids)
    selectedRows.value = []
    $q.notify({ message: 'Records purged', color: 'negative', position: 'top' })
  })
}

const exportSelected = () => {
  historyStore.exportTasks(selectedRows.value.map((r: any) => r.task_id))
  $q.notify({ message: 'Export generated', color: 'positive', position: 'top' })
}

const emptyStateHeading = computed(() => hasFilters.value ? 'No matching records' : 'Intelligence archive empty')
const emptyStateSub = computed(() => hasFilters.value ? 'Try adjusting tactical filters' : 'Start a query to begin building history')

</script>

<style scoped>
.ns-history-search { width: 280px; }
.ns-filter-select { width: 160px; }
.ns-history-table {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
}
.ns-bulk-bar {
  background: var(--ns-bg-elevated);
  border-top: 2px solid var(--ns-accent);
  width: 100%;
  left: 0;
  right: 0;
  z-index: 1000;
  box-shadow: 0 -10px 30px rgba(0,0,0,0.5);
}
.opacity-2 { opacity: 0.2; }
.slide-fade-enter-active, .slide-fade-leave-active { transition: all 0.3s ease-out; }
.slide-fade-enter-from, .slide-fade-leave-to { transform: translateY(100%); opacity: 0; }
.color-primary { color: var(--ns-accent); }
</style>

