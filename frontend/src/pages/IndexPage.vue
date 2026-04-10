<template>
  <q-page class="flex flex-center q-pa-md">
    <div class="full-width" style="max-width: 800px">
      <div class="text-h4 text-weight-bold text-white q-mb-md">
        Digital Intelligence Aggregator
      </div>
      <p class="text-grey-5 q-mb-xl">
        Enter a domain, IP, or URL to begin a deep OSINT investigation. NexusScope will coordinate distributed workers to gather intelligence.
      </p>

      <q-card class="bg-grey-10 text-white q-pa-lg shadow-24 border-indigo">
        <q-form @submit="onSubmit" class="row q-col-gutter-md">
          <div class="col-12 col-sm-8">
            <q-input
              filled
              v-model="target"
              label="Investigation Target"
              placeholder="e.g. google.com"
              dark
              color="indigo"
              :rules="[val => !!val || 'Target is required']"
            />
          </div>
          <div class="col-12 col-sm-4">
            <q-select
              filled
              v-model="type"
              :options="['dns', 'web', 'image']"
              label="Task Type"
              dark
              color="indigo"
            />
          </div>
          <div class="col-12">
            <q-btn
              label="Launch Investigation"
              type="submit"
              color="indigo-7"
              class="full-width q-py-md"
              icon-right="rocket_launch"
              :loading="loading"
            />
          </div>
        </q-form>
      </q-card>

      <div class="q-mt-xl">
        <div class="text-h6 text-white q-mb-sm">Recent Investigations</div>
        <q-list bordered separator class="bg-grey-10 text-white rounded-borders">
          <q-item v-for="task in investigations" :key="task.id">
            <q-item-section avatar>
              <q-icon name="radar" color="indigo" />
            </q-item-section>
            <q-item-section>
              <q-item-label>{{ task.target }}</q-item-label>
              <q-item-label caption class="text-grey-5">{{ task.type }}</q-item-label>
            </q-item-section>
            <q-item-section side>
              <q-badge :color="getStatusColor(task.status)">
                {{ task.status }}
              </q-badge>
            </q-item-section>
          </q-item>
        </q-list>
      </div>
    </div>
  </q-page>
</template>

<script>
import { defineComponent, ref } from 'vue'
import { useQuasar } from 'quasar'

export default defineComponent({
  name: 'IndexPage',
  setup () {
    const $q = useQuasar()
    const target = ref('')
    const type = ref('dns')
    const loading = ref(false)
    const investigations = ref([
      { id: 1, target: 'example.com', type: 'dns', status: 'completed' },
      { id: 2, target: 'nexus.local', type: 'web', status: 'processing' }
    ])

    const onSubmit = () => {
      loading.value = true
      $q.notify({
        message: `Investigation started for ${target.value}`,
        color: 'indigo',
        position: 'top'
      })
      
      // Simulation: In production, call the API
      setTimeout(() => {
        loading.value = false
        investigations.value.unshift({
          id: Date.now(),
          target: target.value,
          type: type.value,
          status: 'pending'
        })
      }, 1000)
    }

    const getStatusColor = (status) => {
      switch (status) {
        case 'completed': return 'positive'
        case 'processing': return 'warning'
        case 'pending': return 'blue'
        default: return 'grey'
      }
    }

    return {
      target,
      type,
      loading,
      investigations,
      onSubmit,
      getStatusColor
    }
  }
})
</script>

<style scoped>
.border-indigo {
  border: 1px solid #3f51b5;
}
</style>
