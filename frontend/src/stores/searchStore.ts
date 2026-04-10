import { defineStore } from 'pinia';
import { ref } from 'vue';
import { apiService, Module } from 'src/services/apiService';
import { useAppStore } from './appStore';

export const useSearchStore = defineStore('search', () => {
  const appStore = useAppStore();

  // --- STATE ---
  const selectedModule = ref<Module>('domain');
  const targetInput = ref('');
  const moduleOptions = [
    { label: 'USERNAME RECON', value: 'username' },
    { label: 'DOMAIN ANALYSIS', value: 'domain' },
    { label: 'IP INTELLIGENCE', value: 'ip' },
    { label: 'METADATA EXTRACTION', value: 'metadata' },
    { label: 'GEOLOCATION', value: 'geolocation' },
    { label: 'WEB SCRAPER', value: 'scraper' }
  ];
  const isDispatching = ref(false);
  const lastError = ref<string | null>(null);
  const lastTaskId = ref<string | null>(null);

  // --- ACTIONS ---
  function setModule(module: Module) {
    selectedModule.value = module;
  }

  function updateTarget(value: string) {
    targetInput.value = value;
  }

  async function dispatchQuery(options: Record<string, any> = {}) {
    isDispatching.value = true;
    lastError.value = null;
    try {
      const response = await apiService.createTask(selectedModule.value, targetInput.value, options);
      lastTaskId.value = response.task_id;
      appStore.incrementActiveTaskCount();
      return response.task_id;
    } catch (error: any) {
      lastError.value = error.response?.data?.message || 'FAILED TO INITIATE TACTICAL QUERY';
      throw error;
    } finally {
      isDispatching.value = false;
    }
  }

  function clearError() {
    lastError.value = null;
  }

  return {
    selectedModule,
    targetInput,
    moduleOptions,
    isDispatching,
    lastError,
    lastTaskId,
    setModule,
    updateTarget,
    dispatchQuery,
    clearError
  };
});
