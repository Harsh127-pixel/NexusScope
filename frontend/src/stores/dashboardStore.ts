import { defineStore } from 'pinia';
import { ref } from 'vue';
import { Task } from 'src/services/apiService';

export const useDashboardStore = defineStore('dashboard', () => {
  // --- STATE ---
  const recentTasks = ref<Task[]>([]);
  const stats = ref({
    totalQueries: 0,
    activeTasks: 0,
    avgResolutionMs: 0,
    modulesOnline: 9
  });

  const systemStatus = ref({
    api: { status: 'OFFLINE', latency: '---' },
    queue: { status: 'STABLE', tasks: 0 },
    tor: { status: 'INACTIVE', port: '9050' },
    firestore: { status: 'CONNECTED', throughput: '---' }
  });

  // --- ACTIONS ---
  async function fetchDashboardData() {
    recentTasks.value = [];
  }

  async function refreshStats() {
    // Intentionally static for the dashboard mock.
  }

  return {
    recentTasks,
    stats,
    systemStatus,
    fetchDashboardData,
    refreshStats
  };
});
