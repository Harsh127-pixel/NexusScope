import { api } from 'src/boot/axios';
import { Notify } from 'quasar';
import { AxiosError, AxiosResponse } from 'axios';

// --- TYPES ---
export type Module = 'username' | 'domain' | 'ip' | 'metadata' | 'scraper' | 'darkweb' | 'phone' | 'email' | 'deepsearch' | 'geolocation';
export type TaskStatus = 'queued' | 'processing' | 'completed' | 'failed';

export interface Task {
  task_id: string;
  module: Module;
  target: string;
  status: TaskStatus;
  result: Record<string, any> | null;
  error: string | null;
  created_at: string;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface TaskStatusResponse {
  task_id: string;
  module: Module;
  target: string;
  status: TaskStatus;
  result: Record<string, any> | null;
  error: string | null;
}

export interface HistoryParams {
  search?: string;
  module?: string;
  status?: string;
  page: number;
  limit: number;
}

// --- API SERVICE ---
class ApiService {
  async healthCheck(): Promise<{ status: string; version: string }> {
    const { data } = await api.get('/health');
    return data;
  }

  async createTask(module: string, target: string, options: Record<string, any> = {}): Promise<{ task_id: string }> {
    const { data } = await api.post('/api/v1/investigations', {
      module,
      type: module,
      target,
      proxy: options.proxy,
      options,
    });
    return data;
  }

  async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    const { data } = await api.get(`/api/v1/investigations/${taskId}`);
    return data;
  }

  async getTaskHistory(params: HistoryParams): Promise<{ tasks: Task[]; total: number }> {
    const { data } = await api.get('/api/v1/history', { params });
    return data;
  }

  async deleteTask(taskId: string): Promise<void> {
    await api.delete(`/api/v1/investigations/${taskId}`);
  }

  async getApiToken(): Promise<{ token: string }> {
    const { data } = await api.get('/api/v1/chatbot/token');
    return data;
  }
}

export const apiService = new ApiService();
