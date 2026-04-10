import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { apiService } from 'src/services/apiService';

export type ApiStatus = 'connected' | 'offline' | 'checking';

export const useAppStore = defineStore('app', () => {
  // --- STATE ---
  const sidebarCollapsed = ref(false);
  const currentPageTitle = ref('DASHBOARD');
  const apiStatus = ref<ApiStatus>('checking');
  const activeTaskCount = ref(0);

  // --- GETTERS ---
  const isApiConnected = computed(() => apiStatus.value === 'connected');

  // --- ACTIONS ---
  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value;
  }

  function setSidebar(value: boolean) {
    sidebarCollapsed.value = value;
  }

  function setPageTitle(title: string) {
    currentPageTitle.value = title;
  }

  async function checkApiHealth() {
    apiStatus.value = 'checking';
    try {
      await apiService.healthCheck();
      apiStatus.value = 'connected';
    } catch (error) {
      // Retry once
      setTimeout(async () => {
        try {
          await apiService.healthCheck();
          apiStatus.value = 'connected';
        } catch (e) {
          apiStatus.value = 'offline';
        }
      }, 2000);
    }
  }

  function incrementActiveTaskCount() {
    activeTaskCount.value++;
  }

  function decrementActiveTaskCount() {
    if (activeTaskCount.value > 0) activeTaskCount.value--;
  }

  return {
    sidebarCollapsed,
    currentPageTitle,
    apiStatus,
    activeTaskCount,
    isApiConnected,
    toggleSidebar,
    setSidebar,
    setPageTitle,
    checkApiHealth,
    incrementActiveTaskCount,
    decrementActiveTaskCount
  };
});
