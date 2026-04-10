import { defineStore } from 'pinia';
import { ref } from 'vue';
import { apiService, TaskStatusResponse } from 'src/services/apiService';
import { useAppStore } from './appStore';

export const useResultsStore = defineStore('results', () => {
  const appStore = useAppStore();

  // --- STATE ---
  const taskId = ref<string | null>(null);
  const taskData = ref<TaskStatusResponse | null>(null);
  const isPolling = ref(false);
  const pollInterval = ref<any>(null);
  const logs = ref<string[]>([]);

  // --- ACTIONS ---
  async function startPolling(id: string) {
    if (pollInterval.value) stopPolling();

    taskId.value = id;
    isPolling.value = true;
    logs.value = [];
    appendLog('INITIATING TELEMETRY SYNCHRONIZATION...');

    pollInterval.value = setInterval(async () => {
      try {
        const response = await apiService.getTaskStatus(id);
        taskData.value = response;

        if (response.status === 'completed') {
          appendLog('TACTICAL DATA ACQUISITION COMPLETE.');
          stopPolling();
          appStore.decrementActiveTaskCount();
        } else if (response.status === 'failed') {
          appendLog(`CRITICAL ERROR: ${response.error || 'TASK_EXECUTION_FAULT'}`);
          stopPolling();
          appStore.decrementActiveTaskCount();
        } else {
          appendLog(`POLLING STATUS: ${response.status.toUpperCase()}...`);
        }
      } catch (error) {
        appendLog('TELEMETRY DROPOUT: RETRYING CONNECTION...');
      }
    }, 2000);
  }

  function stopPolling() {
    if (pollInterval.value) {
      clearInterval(pollInterval.value);
      pollInterval.value = null;
    }
    isPolling.value = false;
  }

  function appendLog(msg: string) {
    const timestamp = new Date().toLocaleTimeString();
    logs.value.push(`[${timestamp}] ${msg}`);
  }

  return {
    taskId,
    taskData,
    isPolling,
    logs,
    startPolling,
    stopPolling,
    appendLog
  };
});
