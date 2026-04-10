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
    appendLog('INITIATING API STATUS SYNC...');

    pollInterval.value = setInterval(async () => {
      try {
        const response = await apiService.getTaskStatus(id);
        taskData.value = response;

        if (response.status === 'completed') {
          appendLog('API EXECUTION COMPLETE.');
          stopPolling();
          appStore.decrementActiveTaskCount();
        } else if (response.status === 'failed') {
          appendLog(`CRITICAL ERROR: ${response.error || 'REQUEST_EXECUTION_FAULT'}`);
          stopPolling();
          appStore.decrementActiveTaskCount();
        } else {
          appendLog(`API STATUS: ${response.status.toUpperCase()}...`);
        }
      } catch (error) {
        appendLog('API SYNC DROPOUT: RETRYING CONNECTION...');
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

  function reset() {
    stopPolling();
    taskId.value = null;
    taskData.value = null;
    logs.value = [];
  }

  return {
    taskId,
    taskData,
    isPolling,
    logs,
    startPolling,
    stopPolling,
    appendLog,
    reset
  };
});
