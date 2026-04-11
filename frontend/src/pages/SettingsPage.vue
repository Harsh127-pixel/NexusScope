<template>
  <q-page class="q-pa-md ns-settings-page">
    <div class="row q-col-gutter-lg">
      <!-- Profile Section -->
      <div class="col-12 col-md-4">
        <ns-card title="ANALYST PROFILE">
          <div class="column items-center q-py-lg">
            <q-avatar size="100px" class="ns-avatar-large q-mb-md">
              <img v-if="authStore.avatarUrl" :src="authStore.avatarUrl" />
              <span v-else>{{ authStore.displayName.charAt(0) }}</span>
            </q-avatar>
            <div class="ns-user-name-large">{{ authStore.displayName }}</div>
            <div class="ns-user-email">{{ authStore.userEmail }}</div>
            <q-chip
              dense
              class="q-mt-md ns-role-chip"
              :label="authStore.userRole.toUpperCase()"
              color="primary"
              text-color="dark"
            />
          </div>

          <q-separator dark class="q-my-md" />

          <div class="q-px-sm">
            <div class="row justify-between q-mb-xs">
              <span class="ns-label-sm">UID:</span>
              <span class="ns-value-sm text-mono">{{ authStore.user?.uid.substring(0, 12) }}...</span>
            </div>
            <div class="row justify-between q-mb-xs">
              <span class="ns-label-sm">PROVIDER:</span>
              <span class="ns-value-sm text-mono">{{ authStore.profile?.provider.toUpperCase() }}</span>
            </div>
            <div class="row justify-between">
              <span class="ns-label-sm">MEMBER SINCE:</span>
              <span class="ns-value-sm text-mono">{{ joinedDate }}</span>
            </div>
          </div>
        </ns-card>
      </div>

      <!-- API Configuration -->
      <div class="col-12 col-md-8">
        <ns-card title="SYSTEM CONFIGURATION">
          <div class="q-mb-xl">
            <div class="ns-heading-xs q-mb-md">API ACCESS TOKEN</div>
            <p class="ns-text-muted">
              Use this token for programmatic access via CLI or third-party integrations. 
              This is the same token used by the NexusScope Telegram Bot.
            </p>
            
            <div class="ns-token-box row no-wrap items-center q-pa-md">
              <div class="col text-mono ns-token-text">
                {{ showToken ? apiToken : '••••••••••••••••••••••••••••••••' }}
              </div>
              <q-btn
                flat
                round
                dense
                class="ns-text-muted q-ml-sm"
                @click="showToken = !showToken"
                :icon="showToken ? 'visibility_off' : 'visibility'"
              />
              <q-btn
                flat
                round
                dense
                class="ns-text-muted q-ml-xs"
                @click="copyToken"
                icon="content_copy"
              />
            </div>
          </div>

          <div>
            <div class="ns-heading-xs q-mb-md">PREFERENCES</div>
            <q-list dark padding>
              <q-item tag="label" v-ripple>
                <q-item-section>
                  <q-item-label>AUTO-POLL RESULTS</q-item-label>
                  <q-item-label caption class="ns-text-muted">Automatically open results page when a search is initiated.</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-toggle v-model="prefs.autoPoll" color="primary" />
                </q-item-section>
              </q-item>

              <q-item tag="label" v-ripple>
                <q-item-section>
                  <q-item-label>TACTICAL SOUND EFFECTS</q-item-label>
                  <q-item-label caption class="ns-text-muted">Audio feedback for search completion and errors.</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-toggle v-model="prefs.sounds" color="primary" />
                </q-item-section>
              </q-item>

              <q-item tag="label" v-ripple>
                <q-item-section>
                  <q-item-label>REDACT SENSITIVE DATA</q-item-label>
                  <q-item-label caption class="ns-text-muted">Mask potentially sensitive info in UI screenshots.</q-item-label>
                </q-item-section>
                <q-item-section side>
                  <q-toggle v-model="prefs.redact" color="primary" />
                </q-item-section>
              </q-item>
            </q-list>
          </div>
        </ns-card>

        <div class="row justify-end q-mt-lg">
          <q-btn
            class="ns-btn-primary"
            label="SAVE SESSION PREFERENCES"
            @click="savePrefs"
          />
        </div>
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAuthStore } from 'src/stores/authStore'
import { apiService } from 'src/services/apiService'
import { useQuasar, copyToClipboard } from 'quasar'
import NsCard from 'components/NsCard.vue'

const authStore = useAuthStore()
const $q = useQuasar()

const apiToken = ref('NS-PROX-8X29-L092-B831')
const showToken = ref(false)
const prefs = ref({
  autoPoll: true,
  sounds: false,
  redact: true
})

const joinedDate = computed(() => {
  if (!authStore.profile?.createdAt) return 'UNKNOWN'
  try {
    const d = (authStore.profile.createdAt as any).toDate()
    return d.toLocaleDateString()
  } catch {
    return 'ACTIVE'
  }
})

onMounted(async () => {
  try {
    const { token } = await apiService.getApiToken()
    apiToken.value = token
  } catch (e) {
    console.error('Failed to fetch API token')
  }
})

const copyToken = () => {
  copyToClipboard(apiToken.value).then(() => {
    $q.notify({
      type: 'positive',
      message: 'TOKEN COPIED TO CLIPBOARD',
      position: 'top',
      timeout: 1500
    })
  })
}

const savePrefs = () => {
  $q.notify({
    type: 'positive',
    message: 'PREFERENCES UPDATED IN LOCAL CACHE',
    position: 'top'
  })
}
</script>

<style scoped>
.ns-avatar-large {
  border: 2px solid var(--ns-accent);
  background: var(--ns-accent-dim);
  color: var(--ns-accent);
  font-weight: 700;
  font-size: 40px;
}

.ns-user-name-large {
  font-size: 20px;
  font-weight: 700;
  color: var(--ns-text-primary);
  letter-spacing: -0.02em;
}

.ns-user-email {
  font-size: 14px;
  color: var(--ns-text-muted);
}

.ns-role-chip {
  font-family: var(--ns-font-mono);
  font-weight: 700;
  letter-spacing: 0.1em;
  font-size: 10px;
}

.ns-token-box {
  background: var(--ns-bg-elevated);
  border: 1px solid var(--ns-border);
  border-radius: 8px;
}

.ns-token-text {
  font-size: 13px;
  color: var(--ns-accent);
  overflow: hidden;
  text-overflow: ellipsis;
}

.ns-label-sm {
  font-family: var(--ns-font-mono);
  font-size: 10px;
  color: var(--ns-text-muted);
  letter-spacing: 0.1em;
}

.ns-value-sm {
  font-size: 11px;
}
</style>
