import { defineStore } from 'pinia';
import { ref } from 'vue';
import { Task } from 'src/services/apiService';

export const useDashboardStore = defineStore('dashboard', () => {
  // --- STATE ---
  const recentTasks = ref<Task[]>([]);
  const stats = ref({
    totalQueries: 1248,
    activeTasks: 3,
    avgResolutionMs: 4800,
    modulesOnline: 6
  });

  const systemStatus = ref({
    api: { status: 'ONLINE', latency: '24ms' },
    redis: { status: 'STABLE', tasks: 12 },
    firestore: { status: 'CONNECTED', throughput: '1.2k req/s' }
  });

  // --- ACTIONS ---
  async function fetchDashboardData() {
    // Mocking realistic data fetch
    recentTasks.value = [
      { 
        task_id: '84f2c91a', module: 'domain', target: 'nexus.local', 
        status: 'completed', result: {}, error: null, 
        created_at: '2026-04-10T10:00:00Z', completed_at: '2026-04-10T10:00:02Z', duration_ms: 2400 
      },
      { 
        task_id: '9a1b3c4d', module: 'ip', target: '8.8.8.8', 
        status: 'processing', result: null, error: null, 
        created_at: '2026-04-10T11:30:00Z', completed_at: null, duration_ms: null 
      },
      { 
        task_id: '3e6c9d2f', module: 'username', target: 'johndoe_osint', 
        status: 'queued', result: null, error: null, 
        created_at: '2026-04-10T11:45:00Z', completed_at: null, duration_ms: null 
      },
      { 
        task_id: '7d2d8f1e', module: 'scraper', target: 'https://intelligence.io', 
        status: 'failed', result: null, error: 'TIMEOUT_ERR', 
        created_at: '2026-04-10T09:15:00Z', completed_at: '2026-04-10T09:16:00Z', duration_ms: 60000 
      },
      { 
        task_id: '1f5e0c4a', module: 'metadata', target: 'evidence_001.jpg', 
        status: 'completed', result: {}, error: null, 
        created_at: '2026-04-10T08:00:00Z', completed_at: '2026-04-10T08:00:01Z', duration_ms: 800 
      },
      { 
        task_id: 'bb22cc33', module: 'geolocation', target: '48.8584,2.2945', 
        status: 'completed', result: {}, error: null, 
        created_at: '2026-04-09T22:00:00Z', completed_at: '2026-04-09T22:00:03Z', duration_ms: 3100 
      },
      { 
        task_id: 'aa11bb22', module: 'domain', target: 'target-alpha.com', 
        status: 'completed', result: {}, error: null, 
        created_at: '2026-04-09T21:00:00Z', completed_at: '2026-04-09T21:00:05Z', duration_ms: 5200 
      },
      { 
        task_id: 'ff44ee55', module: 'ip', target: '1.1.1.1', 
        status: 'processing', result: null, error: null, 
        created_at: '2026-04-10T11:58:00Z', completed_at: null, duration_ms: null 
      },
      { 
        task_id: 'dd11ee22', module: 'username', target: 'shadow_investigator', 
        status: 'completed', result: {}, error: null, 
        created_at: '2026-04-09T20:00:00Z', completed_at: '2026-04-09T20:00:04Z', duration_ms: 4100 
      },
      { 
        task_id: '9988ff22', module: 'scraper', target: 'https://darkweb-check.onion', 
        status: 'failed', result: null, error: 'PROXY_UNREACHABLE', 
        created_at: '2026-04-09T18:00:00Z', completed_at: '2026-04-09T18:01:00Z', duration_ms: 60000 
      }
    ];
  }

  async function refreshStats() {
    // Simulation of stats update
    stats.value.totalQueries += Math.floor(Math.random() * 5);
  }

  return {
    recentTasks,
    stats,
    systemStatus,
    fetchDashboardData,
    refreshStats
  };
});
