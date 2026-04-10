import { boot } from 'quasar/wrappers';
import axios, { AxiosInstance } from 'axios';
import { useAppStore } from 'src/stores/appStore';

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

  // Add the X-NexusScope-Version header to all requests
  api.interceptors.request.use((config) => {
    config.headers['X-NexusScope-Version'] = import.meta.env.VITE_APP_VERSION || '1.0.0';
    return config;
  });

  // Global response handling
  api.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response) {
        if (error.response.status === 401) {
          // Future: Clear session and redirect to login
          console.warn('AUTH_INVALID: Session expired');
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
