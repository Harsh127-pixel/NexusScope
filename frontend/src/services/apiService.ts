import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';
import { Notify } from 'quasar';

// --- TYPES ---
export type Module = 'username' | 'domain' | 'ip' | 'metadata' | 'scraper' | 'darkweb' | 'phone' | 'email';
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
  private axiosInstance: AxiosInstance;

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: import.meta.env.VITE_API_BASE_URL || 'https://nexusscope-backend.onrender.com',
      timeout: 15000,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors() {
    this.axiosInstance.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        // Add auth tokens if needed here
        return config;
      },
      (error: AxiosError) => Promise.reject(error)
    );

    this.axiosInstance.interceptors.response.use(
      (response: AxiosResponse) => response,
      (error: AxiosError) => {
        if (error.response) {
          const status = error.response.status;
          if (status === 500) {
            Notify.create({
              type: 'negative',
              message: 'TACTICAL SYSTEM ERROR: 500 | INTERNAL SERVER FAULT',
              position: 'top',
            });
          } else if (status === 422) {
            // Handled at form level usually
          }
        } else if (error.request) {
          // Network errors handled by store checkApiHealth
        }
        return Promise.reject(error);
      }
    );
  }

  async healthCheck(): Promise<{ status: string; version: string }> {
    const { data } = await this.axiosInstance.get('/health');
    return data;
  }

  async createTask(module: string, target: string, options: Record<string, any> = {}): Promise<{ task_id: string }> {
    const { data } = await this.axiosInstance.post('/api/v1/investigations', {
      module,
      type: module,
      target,
      proxy: options.proxy,
      options,
    });
    return data;
  }

  async getTaskStatus(taskId: string): Promise<TaskStatusResponse> {
    const { data } = await this.axiosInstance.get(`/api/v1/investigations/${taskId}`);
    return data;
  }

  async getTaskHistory(params: HistoryParams): Promise<{ tasks: Task[]; total: number }> {
    const { data } = await this.axiosInstance.get('/api/v1/history', { params });
    return data;
  }

  async deleteTask(taskId: string): Promise<void> {
    await this.axiosInstance.delete(`/api/v1/investigations/${taskId}`);
  }
}

export const apiService = new ApiService();
