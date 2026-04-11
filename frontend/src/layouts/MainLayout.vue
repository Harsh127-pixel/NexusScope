<template>
  <q-layout view="lHh Lpr lFf" class="ns-layout">
    <!-- TOP HEADER -->
    <q-header class="ns-header">
      <q-toolbar class="q-px-md">
        <!-- Hamburger for mobile -->
        <q-btn
          v-if="$q.screen.lt.md"
          flat round dense
          class="q-mr-sm ns-text-muted"
          @click="drawerOpen = !drawerOpen"
          aria-label="Toggle Menu"
        >
          <Menu :size="20" />
        </q-btn>

        <!-- Page Title (Left) -->
        <div class="ns-page-title ns-heading-sm">
          {{ route.meta.title || 'Dashboard' }}
        </div>

        <q-space />

        <!-- Global Search (Center, hidden on mobile) -->
        <div v-if="$q.screen.gt.sm" class="ns-global-search">
          <q-input
            v-model="searchQuery"
            dense
            filled
            placeholder="SEARCH TARGETS, IPS, DOMAINS..."
            class="ns-search-input"
          >
            <template v-slot:prepend>
              <Search :size="16" class="ns-text-muted" />
            </template>
          </q-input>
        </div>

        <q-space />

        <!-- Actions (Right) -->
        <div class="row q-gutter-x-sm items-center">
          <!-- Task Queue Indicator -->
          <div class="ns-task-indicator cursor-pointer q-mr-md" role="status" aria-label="Active Investigations">
            <Layers :size="18" />
            <q-badge v-if="appStore.activeTaskCount > 0" color="primary" floating rounded>
              {{ appStore.activeTaskCount }}
            </q-badge>
            <q-tooltip>ACTIVE INVESTIGATIONS</q-tooltip>
          </div>

          <!-- API Status Chip -->
          <div :class="['ns-status-chip', appStore.isApiConnected ? 'is-connected' : 'is-offline']" role="status">
            <div class="status-dot"></div>
            <span v-if="$q.screen.gt.sm">{{ appStore.isApiConnected ? 'CONNECTED' : 'OFFLINE' }}</span>
          </div>

          <!-- User Profile -->
          <q-btn flat no-caps class="q-ml-sm ns-user-btn" v-if="authStore.isLoggedIn">
            <q-avatar size="28px" class="ns-avatar">
              <img v-if="authStore.avatarUrl" :src="authStore.avatarUrl" alt="P">
              <span v-else>{{ authStore.displayName.charAt(0) }}</span>
            </q-avatar>
            <div class="column q-ml-sm gt-xs ns-user-info">
              <span class="ns-user-name">{{ authStore.displayName }}</span>
              <span class="ns-user-role">{{ authStore.userRole.toUpperCase() }}</span>
            </div>
            
            <q-menu class="ns-user-menu" :offset="[0, 10]">
              <q-list style="min-width: 180px">
                <q-item clickable v-ripple to="/settings">
                  <q-item-section avatar><Settings :size="16"/></q-item-section>
                  <q-item-section>PROFILE SETTINGS</q-item-section>
                </q-item>
                <q-separator dark />
                <q-item clickable v-ripple class="text-negative" @click="handleLogout">
                  <q-item-section avatar><LogOut :size="16"/></q-item-section>
                  <q-item-section>SIGN OUT</q-item-section>
                </q-item>
              </q-list>
            </q-menu>
          </q-btn>
        </div>
      </q-toolbar>
    </q-header>

    <!-- LEFT SIDEBAR -->
    <q-drawer
      v-model="drawerOpen"
      show-if-above
      :mini="appStore.sidebarCollapsed && $q.screen.gt.sm"
      :width="240"
      :mini-width="56"
      :behavior="$q.screen.lt.md ? 'mobile' : 'desktop'"
      class="ns-sidebar"
    >
      <div class="column full-height no-wrap">
        <!-- Sidebar Header -->
        <div class="ns-sidebar-header row items-center no-wrap q-px-md">
          <div class="logomark-container row items-center no-wrap">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="ns-logomark" aria-hidden="true">
              <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2"/>
              <circle cx="12" cy="12" r="2" fill="currentColor"/>
              <path d="M12 3V5M12 19V21M3 12H5M19 12H21" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <div v-if="!appStore.sidebarCollapsed" class="ns-wordmark q-ml-sm ns-heading-sm">
              NEXUS<span>SCOPE</span>
            </div>
          </div>
          
          <q-space />
          
          <q-btn
            v-if="!appStore.sidebarCollapsed"
            flat
            dense
            round
            class="ns-collapse-toggle"
            @click="appStore.toggleSidebar"
            aria-label="Collapse Sidebar"
          >
            <ChevronLeft :size="18" />
          </q-btn>
        </div>

        <!-- Navigation Menu -->
        <q-scroll-area class="col">
          <q-list padding class="ns-nav-list" role="navigation">
            <q-item
              v-for="item in navItems"
              :key="item.path"
              clickable
              v-ripple
              :to="item.path"
              active-class="ns-nav-active"
              class="ns-nav-item"
              :aria-label="item.label"
            >
              <q-item-section avatar>
                <component :is="item.icon" :size="20" aria-hidden="true" />
                <q-tooltip v-if="appStore.sidebarCollapsed" anchor="center right" self="center left">
                  {{ item.label }}
                </q-tooltip>
              </q-item-section>
              <q-item-section v-if="!appStore.sidebarCollapsed">
                {{ item.label }}
              </q-item-section>
            </q-item>
          </q-list>
        </q-scroll-area>

        <q-space />

        <!-- Sidebar Footer -->
        <div class="ns-sidebar-footer q-pa-sm">
          <div v-if="appStore.sidebarCollapsed" class="column items-center">
            <q-btn flat dense round @click="appStore.toggleSidebar" aria-label="Expand Sidebar">
              <ChevronRight :size="18" />
            </q-btn>
            <div class="status-dot q-mt-xs" :class="{ 'bg-green': appStore.isApiConnected, 'bg-red': !appStore.isApiConnected }" role="status"></div>
          </div>
          <div v-else class="row items-center justify-between q-px-sm">
            <div class="ns-version">v1.0.0</div>
            <div class="row items-center">
              <div class="status-dot q-mr-xs" :class="{ 'bg-green': appStore.isApiConnected, 'bg-red': !appStore.isApiConnected }" role="status"></div>
              <span class="ns-label" style="font-size: 10px">{{ appStore.isApiConnected ? 'SECURE' : 'DISCONNECTED' }}</span>
            </div>
          </div>
        </div>
      </div>
    </q-drawer>

    <!-- MAIN CONTENT -->
    <q-page-container class="ns-content-container">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useQuasar } from 'quasar'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from 'src/stores/appStore'
import { useAuthStore } from 'src/stores/authStore'
import { 
  LayoutDashboard, 
  Search, 
  Clock, 
  Layers, 
  Activity, 
  Settings,
  ChevronLeft,
  ChevronRight,
  Menu,
  LogOut
} from 'lucide-vue-next'

const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const authStore = useAuthStore()

const drawerOpen = ref(true)
const searchQuery = ref('')

const navItems = [
  { label: 'DASHBOARD', icon: LayoutDashboard, path: '/' },
  { label: 'INTELLIGENCE SEARCH', icon: Search, path: '/search' },
  { label: 'TASK HISTORY', icon: Clock, path: '/history' },
  { label: 'SYSTEM STATUS', icon: Activity, path: '/status' },
  { label: 'SETTINGS', icon: Settings, path: '/settings' }
]

// Auth Handlers
const handleLogout = async () => {
  await authStore.logout()
}

// Handle Responsive Collapse
const handleResize = () => {
  if (window.innerWidth < 900) {
    appStore.setSidebar(true)
  }
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  handleResize()
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})
</script>

<style lang="css">
.ns-layout {
  background-color: var(--ns-bg-base);
}

.ns-header {
  background-color: var(--ns-bg-base) !important;
  border-bottom: 1px solid var(--ns-border);
  height: 56px;
  color: var(--ns-text-primary);
}

.ns-sidebar {
  background-color: var(--ns-bg-surface) !important;
  border-right: 1px solid var(--ns-border);
}

.ns-sidebar-header {
  height: 56px;
  border-bottom: 1px solid var(--ns-border);
}

.ns-logomark {
  color: var(--ns-accent);
}

.ns-wordmark {
  font-family: var(--ns-font-sans);
  font-weight: 700;
  letter-spacing: -0.05em;
  color: var(--ns-text-primary);
}

.ns-wordmark span {
  color: var(--ns-accent);
}

.ns-global-search {
  width: 100%;
  max-width: 480px;
}

.ns-search-input .q-field__control {
  font-family: var(--ns-font-mono);
  font-size: 12px;
  letter-spacing: 0.05em;
}

.ns-status-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  border-radius: 20px;
  background: var(--ns-bg-elevated);
  border: 1px solid var(--ns-border);
  font-family: var(--ns-font-mono);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
}

.ns-status-chip.is-connected { color: var(--ns-green); }
.ns-status-chip.is-offline { color: var(--ns-red); }

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: currentColor;
}

.ns-nav-list {
  padding-top: 20px;
}

.ns-nav-item {
  margin-bottom: 4px;
  color: var(--ns-text-muted);
  font-family: var(--ns-font-mono);
  font-size: 11px;
  letter-spacing: 0.05em;
  transition: var(--ns-transition);
  min-height: 44px;
}

.ns-nav-item:hover {
  background: var(--ns-accent-dim);
  color: var(--ns-text-primary);
}

.ns-nav-active {
  color: var(--ns-accent) !important;
  background: var(--ns-accent-dim) !important;
  border-left: 2px solid var(--ns-accent);
}

.ns-sidebar-footer {
  border-top: 1px solid var(--ns-border);
  background: var(--ns-bg-surface);
}

.ns-version {
  font-family: var(--ns-font-mono);
  font-size: 10px;
  color: var(--ns-text-muted);
}

.ns-content-container {
  background-image: radial-gradient(var(--ns-border) 1px, transparent 1px);
  background-size: 24px 24px;
  min-height: 100vh;
}

/* FADE TRANSITION */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 150ms ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
/* USER PROFILE STYLES */
.ns-user-btn {
  padding: 4px 8px;
  border-radius: 12px;
  transition: background 0.2s;
}

.ns-user-btn:hover {
  background: var(--ns-bg-elevated);
}

.ns-avatar {
  border: 1px solid var(--ns-border);
  background: var(--ns-accent-dim);
  color: var(--ns-accent);
  font-weight: 700;
  font-size: 14px;
}

.ns-user-info {
  line-height: 1.1;
  text-align: left;
}

.ns-user-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--ns-text-primary);
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ns-user-role {
  font-size: 9px;
  font-family: var(--ns-font-mono);
  color: var(--ns-accent);
  letter-spacing: 0.05em;
}

.ns-user-menu {
  background: var(--ns-bg-surface) !important;
  border: 1px solid var(--ns-border);
  box-shadow: 0 10px 30px rgba(0,0,0,0.5);
}
</style>
