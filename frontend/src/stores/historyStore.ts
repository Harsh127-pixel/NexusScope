import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { apiService, Task, HistoryParams } from 'src/services/apiService';

export const useHistoryStore = defineStore('history', () => {
  // --- STATE ---
  const tasks = ref<Task[]>([]);
  const filters = ref({
    search: '',
    module: 'All',
    status: 'All',
    dateRange: null as any
  });
  const pagination = ref({
    page: 1,
    rowsPerPage: 25,
    total: 0
  });

  // --- GETTERS ---
  const filteredTasks = computed(() => {
    return tasks.value.filter(task => {
      // Client-side filtering as a fallback/overlay
      const matchesSearch = !filters.value.search || 
        task.target.toLowerCase().includes(filters.value.search.toLowerCase()) ||
        task.task_id.toLowerCase().includes(filters.value.search.toLowerCase());
      
      const matchesModule = filters.value.module === 'All' || task.module === filters.value.module;
      const matchesStatus = filters.value.status === 'All' || task.status === filters.value.status.toLowerCase();

      return matchesSearch && matchesModule && matchesStatus;
    });
  });

  const selectedTaskIds = ref<string[]>([]);

  // --- ACTIONS ---
  async function fetchHistory() {
    const params: HistoryParams = {
      search: filters.value.search,
      module: filters.value.module === 'All' ? undefined : filters.value.module,
      status: filters.value.status === 'All' ? undefined : filters.value.status,
      page: pagination.value.page,
      limit: pagination.value.rowsPerPage
    };

    try {
      const response = await apiService.getTaskHistory(params);
      tasks.value = response.tasks;
      pagination.value.total = response.total;
    } catch (error) {
      console.error('FAILED TO FETCH ARCHIVE:', error);
    }
  }

  async function deleteTask(id: string) {
    try {
      await apiService.deleteTask(id);
      tasks.value = tasks.value.filter(t => t.task_id !== id);
    } catch (error) {
      console.error('DELETE FAILED:', error);
    }
  }

  async function deleteMany(ids: string[]) {
    // In a real app, you'd have a bulk delete endpoint
    for (const id of ids) {
      await deleteTask(id);
    }
    selectedTaskIds.value = [];
  }

  function exportTasks(ids: string[]) {
    const targets = tasks.value.filter(t => ids.includes(t.task_id));
    const blob = new Blob([JSON.stringify(targets, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `nexus_export_${Date.now()}.json`;
    a.click();
  }

  return {
    tasks,
    filters,
    pagination,
    filteredTasks,
    selectedTaskIds,
    fetchHistory,
    deleteTask,
    deleteMany,
    exportTasks
  };
});
