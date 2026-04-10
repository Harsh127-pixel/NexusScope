<template>
  <q-page class="search-page q-pa-xl">
    <div class="full-width" style="max-width: 1020px; margin: 0 auto">

      <!-- ── PAGE HEADER ──────────────────────────────────────────── -->
      <div class="text-center q-mb-xl">
        <div class="ns-label q-mb-xs">INTELLIGENCE ACQUISITION ENGINE</div>
        <h1 class="ns-heading-lg q-ma-none text-white">Select Theater &amp; Launch</h1>
        <p class="ns-muted q-mt-sm">
          Each theater maps to a specialized class of open-source intelligence tools.
        </p>
      </div>

      <!-- ── THEATER SELECTOR CARDS ───────────────────────────────── -->
      <div class="theater-grid q-mb-xl">
        <!-- Theater 1: Dark Web -->
        <div
          class="theater-card"
          :class="{ 'theater-card--active': searchStore.selectedTheater === 'darkweb', 'theater-card--darkweb': true }"
          @click="searchStore.setTheater('darkweb')"
          id="theater-darkweb"
        >
          <div class="theater-card__icon">🧅</div>
          <div class="theater-card__body">
            <div class="theater-card__label">THEATER I</div>
            <div class="theater-card__name">Dark Web / Onion</div>
            <div class="theater-card__tools">TorBot · Fresh Onions · Onioff · Tor Crawl</div>
          </div>
          <div class="theater-card__badge" v-if="searchStore.selectedTheater === 'darkweb'">ACTIVE</div>
        </div>

        <!-- Theater 2: Recon -->
        <div
          class="theater-card"
          :class="{ 'theater-card--active': searchStore.selectedTheater === 'recon', 'theater-card--recon': true }"
          @click="searchStore.setTheater('recon')"
          id="theater-recon"
        >
          <div class="theater-card__icon">🔍</div>
          <div class="theater-card__body">
            <div class="theater-card__label">THEATER II</div>
            <div class="theater-card__name">General Recon &amp; Footprinting</div>
            <div class="theater-card__tools">GASMask · Skip Tracer · Final Recon · OSINT-SPY</div>
          </div>
          <div class="theater-card__badge" v-if="searchStore.selectedTheater === 'recon'">ACTIVE</div>
        </div>

        <!-- Theater 3: Identity -->
        <div
          class="theater-card"
          :class="{ 'theater-card--active': searchStore.selectedTheater === 'identity', 'theater-card--identity': true }"
          @click="searchStore.setTheater('identity')"
          id="theater-identity"
        >
          <div class="theater-card__icon">🔑</div>
          <div class="theater-card__body">
            <div class="theater-card__label">THEATER III</div>
            <div class="theater-card__name">Identity &amp; Credential Hunting</div>
            <div class="theater-card__tools">h8mail · OSINT-SPY · Sherlock · Social Mapper</div>
          </div>
          <div class="theater-card__badge" v-if="searchStore.selectedTheater === 'identity'">ACTIVE</div>
        </div>
      </div>

      <!-- ── MODULE + INPUT PANEL ─────────────────────────────────── -->
      <q-card flat class="intel-panel q-pa-xl">

        <!-- Module selector tabs within the active theater -->
        <div class="module-tabs q-mb-lg">
          <div
            v-for="mod in searchStore.theaterModules"
            :key="mod.value"
            class="module-tab"
            :class="{ 'module-tab--active': searchStore.selectedModule === mod.value }"
            @click="searchStore.setModule(mod.value)"
            :id="`module-tab-${mod.value}`"
          >
            <component :is="moduleIcon(mod.value)" :size="14" class="q-mr-xs" />
            {{ mod.label }}
          </div>
        </div>

        <!-- Active module description -->
        <transition name="fade-slide" mode="out-in">
          <div :key="searchStore.selectedModule" class="module-desc-block q-mb-lg">
            <div class="row items-center q-gutter-x-sm q-mb-xs">
              <component :is="moduleIcon(searchStore.selectedModule)" :size="20" class="ns-accent-text" />
              <span class="text-white text-weight-medium">{{ searchStore.currentModuleOption.label }}</span>
              <q-badge class="theater-badge" :class="`badge--${searchStore.selectedTheater}`">
                THEATER {{ theaterNum(searchStore.selectedTheater) }}
              </q-badge>
            </div>
            <p class="ns-muted q-ma-none" style="font-size: 13px">
              {{ searchStore.currentModuleOption.description }}
            </p>
          </div>
        </transition>

        <!-- Dark Web: special Tor status warning -->
        <transition name="fade">
          <div v-if="searchStore.selectedTheater === 'darkweb'" class="tor-banner q-mb-lg">
            <div class="row items-center q-gutter-x-sm">
              <span class="tor-dot" :class="torOnline ? 'tor-dot--online' : 'tor-dot--offline'"></span>
              <span v-if="torOnline" class="text-positive text-caption text-mono">TOR PROXY ONLINE — SOCKS5:9050</span>
              <span v-else class="text-warning text-caption text-mono">TOR PROXY OFFLINE — Start Tor service before crawling</span>
            </div>
            <div class="text-caption ns-muted q-mt-xs" style="font-size: 11px">
              All traffic will be routed through <code>socks5://127.0.0.1:9050</code>. Your real IP will be hidden.
            </div>
          </div>
        </transition>

        <!-- HIBP key notice for Identity theater -->
        <transition name="fade">
          <div v-if="searchStore.selectedModule === 'email'" class="hibp-banner q-mb-lg">
            <div class="row items-center q-gutter-x-sm">
              <span class="text-caption text-mono" style="color: var(--ns-accent)">ℹ BREACH DATA</span>
              <span class="text-caption ns-muted">Set <code>HIBP_API_KEY</code> in backend .env for full HaveIBeenPwned breach scans.</span>
            </div>
          </div>
        </transition>

        <!-- ── DYNAMIC PARAMETER FORM ──────────────────────────────── -->
        <q-form @submit="startInvestigation" class="column q-gutter-y-md" id="investigation-form">

          <!-- Main target input (adaptive label/placeholder) -->
          <transition name="fade-slide" mode="out-in">
            <div :key="`input-${searchStore.selectedModule}`">
              <q-input
                v-model="searchStore.targetInput"
                filled
                dark
                :label="inputLabel"
                :placeholder="searchStore.inputPlaceholder"
                class="ns-intel-input"
                :rules="[val => !!val || 'Target is required']"
                id="target-input"
              >
                <template v-slot:prepend>
                  <component :is="moduleIcon(searchStore.selectedModule)" :size="18" class="ns-accent-text" />
                </template>
              </q-input>
            </div>
          </transition>

          <!-- Phone module extras -->
          <transition name="fade">
            <div v-if="searchStore.selectedModule === 'phone'" class="hint-block">
              <span class="text-caption ns-muted">
                Format: <code>+1-555-867-5309</code> or <code>+918001234567</code> — E.164 recommended
              </span>
            </div>
          </transition>

          <!-- Dark Web extras -->
          <transition name="fade">
            <div v-if="searchStore.selectedTheater === 'darkweb'" class="hint-block">
              <span class="text-caption ns-muted">
                Accepts <code>.onion</code> URLs. Standard clearnet URLs will be crawled through Tor exit nodes.
              </span>
            </div>
          </transition>

          <!-- Advanced Config toggle -->
          <div class="row items-center justify-between q-py-sm adv-divider">
            <div class="row items-center">
              <Settings :size="14" class="ns-muted q-mr-sm" />
              <span class="ns-label" style="font-size: 11px">ADVANCED CONFIGURATION</span>
            </div>
            <q-toggle v-model="showAdvanced" color="primary" dense id="advanced-toggle" />
          </div>

          <!-- Advanced Options -->
          <q-slide-transition>
            <div v-if="showAdvanced" class="row q-col-gutter-md q-pt-sm">
              <div class="col-12 col-sm-4" v-if="supportsTimeoutAndProxy">
                <q-input
                  v-model.number="advOptions.timeout"
                  filled dark dense type="number"
                  label="TIMEOUT (SEC)"
                  :min="5" :max="120"
                  class="ns-intel-input"
                  id="timeout-input"
                />
              </div>
              <div class="col-12 col-sm-4 column justify-center" v-if="supportsPlaywright">
                <q-checkbox
                  v-model="advOptions.usePlaywright"
                  label="USE PLAYWRIGHT RENDER"
                  dark color="primary"
                  class="ns-label"
                  id="playwright-toggle"
                />
              </div>
              <div class="col-12 col-sm-4 column justify-center" v-if="supportsTimeoutAndProxy">
                <q-checkbox
                  v-model="advOptions.useProxy"
                  label="CUSTOM PROXY"
                  dark color="primary"
                  class="ns-label"
                  id="proxy-toggle"
                />
              </div>
              <div class="col-12" v-if="showAdvanced && advOptions.useProxy && supportsTimeoutAndProxy">
                <q-input
                  v-model="advOptions.proxy"
                  filled dark dense
                  label="PROXY URL"
                  placeholder="http://user:pass@host:port or socks5://..."
                  class="ns-intel-input"
                  id="proxy-input"
                />
              </div>
            </div>
          </q-slide-transition>

          <!-- Launch Button -->
          <q-btn
            type="submit"
            class="launch-btn full-width q-mt-md"
            :class="`launch-btn--${searchStore.selectedTheater}`"
            :loading="searchStore.isDispatching"
            id="launch-btn"
          >
            <div class="row items-center no-wrap">
              <Zap :size="18" class="q-mr-sm" />
              <span class="text-weight-bold tracking-wide">INITIATE INVESTIGATION</span>
            </div>
          </q-btn>
        </q-form>
      </q-card>

      <!-- ── POST-SUBMIT TERMINAL PREVIEW ─────────────────────────── -->
      <transition name="fade">
        <div v-if="submitted" class="q-mt-xl">
          <div class="ns-label q-mb-md">◉ ACTIVE INVESTIGATION STREAM</div>
          <q-card flat class="terminal-preview q-pa-lg">
            <div class="text-mono text-caption column q-gutter-y-xs">
              <div class="text-positive">[OK] Investigation accepted by API</div>
              <div class="text-white">investigation_id: <span class="ns-accent-text">{{ investigationId }}</span></div>
              <div class="text-white">target: <span class="text-info">{{ searchStore.targetInput }}</span></div>
              <div class="text-white">module: <span class="text-warning">{{ searchStore.selectedModule }}</span></div>
              <div class="text-white">theater: {{ theaterLabel(searchStore.selectedTheater) }}</div>
              <div class="text-blue-4 q-mt-sm blink">▶ Processing in backend worker...</div>
            </div>
            <q-btn
              flat dense
              label="VIEW FULL RESULTS →"
              class="ns-label ns-accent-text q-mt-md"
              :to="'/results/' + investigationId"
              id="view-results-btn"
            />
          </q-card>
        </div>
      </transition>

    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Search, Settings, Zap, Globe, MapPin, Code, User,
  Mail, Phone, Shield, FileSearch, Navigation, Eye
} from 'lucide-vue-next'
import { useQuasar } from 'quasar'
import { useSearchStore, Theater } from 'src/stores/searchStore'
import { Module } from 'src/services/apiService'

const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const searchStore = useSearchStore()

const submitted = ref(false)
const showAdvanced = ref(false)
const investigationId = ref('')
const torOnline = ref<boolean | null>(null)

const advOptions = reactive({
  timeout: 12,
  useProxy: false,
  proxy: '',
  usePlaywright: false,
})

onMounted(async () => {
  // Honor ?module= query param
  if (route.query.module) {
    searchStore.setModule(route.query.module as Module)
  }
  // Ping backend to check Tor status (best-effort)
  try {
    const res = await fetch(
      `${import.meta.env.VITE_API_BASE_URL || 'https://nexusscope-backend.onrender.com'}/health`
    )
    if (res.ok) torOnline.value = false // Real check happens on-demand in backend
  } catch {
    torOnline.value = false
  }
})

const inputLabel = computed(() => {
  const labels: Record<string, string> = {
    domain: 'TARGET DOMAIN',
    ip: 'TARGET IP ADDRESS',
    username: 'TARGET USERNAME',
    metadata: 'IMAGE URL',
    scraper: 'TARGET URL',
    darkweb: 'ONION URL / .onion ADDRESS',
    phone: 'PHONE NUMBER (E.164)',
    email: 'TARGET EMAIL ADDRESS',
  }
  return labels[searchStore.selectedModule] ?? 'INVESTIGATION TARGET'
})

const supportsTimeoutAndProxy = computed(() => 
  ['scraper', 'username', 'metadata'].includes(searchStore.selectedModule)
)

const supportsPlaywright = computed(() => 
  searchStore.selectedModule === 'scraper'
)

function moduleIcon(module: string) {
  const map: Record<string, any> = {
    domain: Globe,
    ip: MapPin,
    username: User,
    metadata: FileSearch,
    geolocation: Navigation,
    scraper: Code,
    darkweb: Eye,
    phone: Phone,
    email: Mail,
  }
  return map[module] ?? Search
}

function theaterNum(theater: Theater) {
  return { darkweb: 'I', recon: 'II', identity: 'III' }[theater]
}

function theaterLabel(theater: Theater) {
  return {
    darkweb: 'Theater I — Dark Web / Onion',
    recon: 'Theater II — General Recon',
    identity: 'Theater III — Identity & Credential',
  }[theater]
}

const startInvestigation = async () => {
  try {
    const id = await searchStore.dispatchQuery({
      timeout: Number(advOptions.timeout) || 12,
      use_playwright: advOptions.usePlaywright,
      proxy: advOptions.useProxy ? advOptions.proxy : undefined,
    })
    investigationId.value = id
    submitted.value = true
    await router.push(`/results/${id}`)

    $q.notify({
      message: `Investigation dispatched — ${searchStore.selectedModule.toUpperCase()} module`,
      color: 'primary',
      position: 'top',
      icon: 'radar',
      timeout: 3000,
    })
  } catch (error) {
    $q.notify({
      message: searchStore.lastError || 'Investigation failed to launch',
      color: 'negative',
      position: 'top',
      timeout: 4000,
    })
  }
}
</script>

<style scoped>
/* ── Layout ───────────────────────────────────────────────── */
.search-page {
  background: var(--ns-bg-base);
  min-height: 100vh;
}

/* ── Theater Grid ─────────────────────────────────────────── */
.theater-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

@media (max-width: 860px) {
  .theater-grid { grid-template-columns: 1fr; }
}

.theater-card {
  position: relative;
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  border-radius: 14px;
  padding: 22px 20px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.theater-card::before {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0;
  transition: opacity 0.25s ease;
  border-radius: inherit;
}

.theater-card--darkweb::before  { background: radial-gradient(circle at top left, rgba(139,92,246,0.18) 0%, transparent 70%); }
.theater-card--recon::before    { background: radial-gradient(circle at top left, rgba(56,189,248,0.12) 0%, transparent 70%); }
.theater-card--identity::before { background: radial-gradient(circle at top left, rgba(249,115,22,0.14) 0%, transparent 70%); }

.theater-card:hover,
.theater-card--active {
  transform: translateY(-3px);
  border-color: transparent;
}

.theater-card--active::before { opacity: 1; }

.theater-card--darkweb.theater-card--active,
.theater-card--darkweb:hover  { border-color: rgba(139,92,246,0.5); box-shadow: 0 0 24px rgba(139,92,246,0.2); }
.theater-card--recon.theater-card--active,
.theater-card--recon:hover    { border-color: rgba(56,189,248,0.5);  box-shadow: 0 0 24px rgba(56,189,248,0.15); }
.theater-card--identity.theater-card--active,
.theater-card--identity:hover { border-color: rgba(249,115,22,0.5);  box-shadow: 0 0 24px rgba(249,115,22,0.18); }

.theater-card__icon {
  font-size: 28px;
  flex-shrink: 0;
  line-height: 1;
}

.theater-card__body { flex: 1; min-width: 0; }

.theater-card__label {
  font-size: 9px;
  font-family: var(--ns-font-mono);
  letter-spacing: 0.15em;
  color: var(--ns-muted);
  margin-bottom: 4px;
}

.theater-card__name {
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  margin-bottom: 6px;
}

.theater-card__tools {
  font-size: 10px;
  font-family: var(--ns-font-mono);
  color: var(--ns-muted);
  line-height: 1.5;
}

.theater-card__badge {
  position: absolute;
  top: 12px;
  right: 12px;
  font-size: 8px;
  font-family: var(--ns-font-mono);
  letter-spacing: 0.12em;
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--ns-accent);
  color: #000;
  font-weight: 700;
}

/* ── Intel Panel ──────────────────────────────────────────── */
.intel-panel {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  border-radius: 16px;
}

/* ── Module Tabs ──────────────────────────────────────────── */
.module-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.module-tab {
  display: flex;
  align-items: center;
  font-size: 10px;
  font-family: var(--ns-font-mono);
  letter-spacing: 0.1em;
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid var(--ns-border);
  color: var(--ns-muted);
  cursor: pointer;
  transition: all 0.18s ease;
  user-select: none;
}

.module-tab:hover {
  border-color: var(--ns-accent);
  color: var(--ns-accent);
}

.module-tab--active {
  background: var(--ns-accent);
  color: #000;
  border-color: var(--ns-accent);
  font-weight: 700;
}

/* ── Module description block ────────────────────────────── */
.module-desc-block {
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--ns-border);
  border-radius: 10px;
  padding: 14px 16px;
}

.theater-badge {
  font-size: 9px;
  font-family: var(--ns-font-mono);
  letter-spacing: 0.1em;
  padding: 2px 8px;
  border-radius: 999px;
}

.badge--darkweb  { background: rgba(139,92,246,0.25) !important; color: #c4b5fd !important; }
.badge--recon    { background: rgba(56,189,248,0.2) !important;  color: #7dd3fc !important; }
.badge--identity { background: rgba(249,115,22,0.2) !important;  color: #fb923c !important; }

/* ── Tor Banner ───────────────────────────────────────────── */
.tor-banner {
  background: rgba(139,92,246,0.08);
  border: 1px solid rgba(139,92,246,0.3);
  border-radius: 10px;
  padding: 12px 16px;
}

.tor-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tor-dot--online  { background: #22c55e; box-shadow: 0 0 8px rgba(34,197,94,0.6); }
.tor-dot--offline { background: #f59e0b; box-shadow: 0 0 8px rgba(245,158,11,0.5); animation: pulse-glow 1.5s infinite; }

@keyframes pulse-glow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ── HIBP Banner ──────────────────────────────────────────── */
.hibp-banner {
  background: rgba(0, 212, 255, 0.05);
  border: 1px solid rgba(0, 212, 255, 0.15);
  border-radius: 10px;
  padding: 10px 14px;
}

/* ── Input ────────────────────────────────────────────────── */
.ns-intel-input { font-family: var(--ns-font-mono); }

/* ── Advanced Divider ─────────────────────────────────────── */
.adv-divider {
  border-top: 1px solid var(--ns-border);
  border-bottom: 1px solid var(--ns-border);
  padding: 10px 0;
}

/* ── Hint Block ───────────────────────────────────────────── */
.hint-block {
  border-left: 2px solid var(--ns-accent);
  padding-left: 12px;
  margin-top: -4px;
}

/* ── Launch Button ────────────────────────────────────────── */
.launch-btn {
  padding: 16px;
  border-radius: 10px;
  font-family: var(--ns-font-mono);
  letter-spacing: 0.12em;
  font-size: 13px;
  transition: all 0.2s ease;
}

.launch-btn--darkweb  { background: linear-gradient(135deg, #7c3aed, #a855f7) !important; color: #fff !important; }
.launch-btn--recon    { background: linear-gradient(135deg, #0284c7, #38bdf8) !important; color: #fff !important; }
.launch-btn--identity { background: linear-gradient(135deg, #c2410c, #f97316) !important; color: #fff !important; }

.launch-btn:hover { transform: translateY(-1px); filter: brightness(1.1); }

/* ── Terminal preview ─────────────────────────────────────── */
.terminal-preview {
  background: #0a0a0f;
  border: 1px solid var(--ns-accent);
  border-radius: 12px;
  box-shadow: 0 0 30px rgba(0,212,255,0.08);
}

/* ── Transitions ──────────────────────────────────────────── */
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.fade-slide-enter-active { transition: all 0.2s ease; }
.fade-slide-leave-active { transition: all 0.15s ease; }
.fade-slide-enter-from { opacity: 0; transform: translateY(6px); transform: translateY(6px); }
.fade-slide-leave-to   { opacity: 0; transform: translateY(-4px); }

.tracking-wide { letter-spacing: 0.12em; }

.blink {
  animation: blink-cursor 1.2s step-end infinite;
}
@keyframes blink-cursor {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
</style>
