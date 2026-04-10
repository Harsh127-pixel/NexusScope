<template>
  <q-page class="q-pa-xl flex flex-center">
    <div class="full-width" style="max-width: 900px">
      <!-- HEADER -->
      <div class="text-center q-mb-xl">
        <div class="ns-label q-mb-xs">INTELLIGENCE ACQUISITION</div>
        <h1 class="ns-heading-lg q-ma-none text-white">Target Investigation</h1>
        <p class="ns-muted q-mt-sm">Enter a target identifier to begin automated data aggregation.</p>
      </div>

      <!-- SEARCH CARD -->
      <q-card flat class="ns-search-container q-pa-xl">
        <q-form @submit="startInvestigation" class="column q-gutter-y-lg">
          <div class="row q-col-gutter-md">
            <!-- Target Input -->
            <div class="col-12 col-md-8">
              <q-input
                v-model="searchStore.targetInput"
                filled
                label="INVESTIGATION TARGET"
                placeholder="DOMAIN, IP, USERNAME, OR URL"
                class="ns-search-input"
                :rules="[val => !!val || 'Target is required']"
              >
                <template v-slot:prepend>
                  <Search :size="20" class="ns-accent-text" />
                </template>
              </q-input>
            </div>

            <!-- Module Selection -->
            <div class="col-12 col-md-4">
              <q-select
                v-model="searchStore.selectedModule"
                :options="searchStore.moduleOptions"
                filled
                label="INTEL MODULE"
                class="ns-search-input"
                emit-value
                map-options
              >
                <template v-slot:option="scope">
                  <q-item v-bind="scope.itemProps" class="ns-nav-item">
                    <q-item-section avatar>
                      <component :is="scope.opt.icon" :size="18" />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label>{{ scope.opt.label }}</q-item-label>
                    </q-item-section>
                  </q-item>
                </template>
              </q-select>
            </div>
          </div>

          <!-- Configuration Toggle -->
          <div class="row items-center justify-between q-py-sm border-y ns-border">
            <div class="row items-center">
              <Settings :size="16" class="ns-muted q-mr-sm" />
              <span class="ns-label">ADVANCED CONFIGURATION</span>
            </div>
            <q-toggle
              v-model="showAdvanced"
              color="primary"
              dense
            />
          </div>

          <!-- Advanced Options (Expandable) -->
          <q-slide-transition>
            <div v-if="showAdvanced" class="row q-col-gutter-md q-pt-md">
              <div class="col-12 col-sm-6">
                <q-input v-model="investigation.timeout" filled type="number" label="TIMEOUT (SEC)" label-color="muted" />
              </div>
              <div class="col-12 col-sm-6">
                <q-checkbox v-model="investigation.useProxy" label="USE TOR EXIT NODES" dark color="primary" class="ns-label" />
              </div>
            </div>
          </q-slide-transition>

          <!-- Launch Button -->
          <q-btn
            type="submit"
            color="primary"
            class="full-width q-py-md ns-launch-btn"
            :loading="searchStore.isDispatching"
          >
            <div class="row items-center no-wrap">
              <Zap :size="18" class="q-mr-sm" />
              <span class="text-weight-bold">INITIATE INVESTIGATION</span>
            </div>
          </q-btn>
        </q-form>
      </q-card>

      <!-- RESULTS PREVIEW (Placeholder) -->
      <transition name="fade">
        <div v-if="submitted" class="q-mt-xl">
          <div class="ns-label q-mb-md">ACTIVE INVESTIGATION STREAM</div>
          <q-card flat class="q-pa-lg ns-terminal-preview bg-black">
            <div class="text-mono text-caption q-gutter-y-xs">
              <div class="text-positive">[SUCCESS] Signal established with Task Broker</div>
              <div class="text-white">investigation_id: {{ investigationId }}</div>
              <div class="text-white">target_acquired: {{ investigation.target }}</div>
              <div class="text-white">module_deploying: {{ investigation.module }}...</div>
              <div class="text-blue animate-pulse q-mt-md">Waiting for worker telemetry...</div>
            </div>
            <q-btn 
              flat 
              dense 
              icon-right="arrow_forward" 
              label="TRACK FULL RESULTS" 
              class="ns-label q-mt-lg" 
              :to="'/results/' + investigationId"
            />
          </q-card>
        </div>
      </transition>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, Settings, Zap, User, Globe, MapPin, FileSearch, Navigation, Code } from 'lucide-vue-next'
import { useQuasar } from 'quasar'
import { useSearchStore } from 'src/stores/searchStore'

const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const searchStore = useSearchStore()

const submitted = ref(false)
const showAdvanced = ref(false)
const investigationId = ref('')

onMounted(() => {
  if (route.query.module) {
    const mod = route.query.module as string
    searchStore.setModule(mod as any)
  }
})

const startInvestigation = async () => {
  try {
    const id = await searchStore.dispatchQuery()
    investigationId.value = id
    submitted.value = true
    
    $q.notify({
      message: 'Investigation Launched Successfully',
      color: 'primary',
      position: 'top',
      icon: 'radar'
    })
  } catch (error) {
    $q.notify({
      message: searchStore.lastError || 'Investigation Failed',
      color: 'negative',
      position: 'top'
    })
  }
}
</script>

<style scoped>
.ns-search-container {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  border-radius: var(--ns-radius-lg);
}

.ns-search-input {
  font-family: var(--ns-font-mono);
}

.ns-launch-btn {
  font-family: var(--ns-font-mono);
  letter-spacing: 0.1em;
}

.ns-terminal-preview {
  border: 1px solid var(--ns-accent);
  box-shadow: var(--ns-accent-glow);
}

.border-y {
  border-top: 1px solid var(--ns-border);
  border-bottom: 1px solid var(--ns-border);
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
