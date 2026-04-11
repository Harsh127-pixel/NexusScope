import { boot } from 'quasar/wrappers';
import axios, { AxiosInstance } from 'axios';
import { useAppStore } from 'src/stores/appStore';
import { useAuthStore } from 'src/stores/authStore';

declare module '@vue/runtime-core' {
  interface ComponentCustomProperties {
    $axios: AxiosInstance;
    $api: AxiosInstance;
  }
}

// Create the tactical axios instance
const api = axios.create({ 
  baseURL: import.meta.env.VITE_API_BASE_URL || 'https://nexusscope-backend.onrender.com',
  timeout: 15000,
});

export default boot(({ app, store }) => {
  const appStore = useAppStore(store);

  // Add headers to all requests
  api.interceptors.request.use(async (config) => {
    config.headers['X-NexusScope-Version'] = import.meta.env.VITE_APP_VERSION || '1.0.0';
    
    // Inject Firebase Token
    const authStore = useAuthStore(store);
    if (authStore.user) {
      const token = await authStore.user.getIdToken();
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    
    return config;
  });

  // Global response handling
  api.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response) {
        if (error.response.status === 401) {
          const authStore = useAuthStore(store);
          authStore.logout(); // Clear state and redirect to login
        } else if (error.response.status === 503) {
          appStore.apiStatus = 'offline';
        }
      } else if (error.request) {
        appStore.apiStatus = 'offline';
      }
      return Promise.reject(error);
    }
  );

  app.config.globalProperties.$axios = axios;
  app.config.globalProperties.$api = api;
});

export { api };
