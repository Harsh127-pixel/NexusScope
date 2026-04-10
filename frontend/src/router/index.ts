import { route } from 'quasar/wrappers';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';
import routes from './routes';
import { useAppStore } from 'src/stores/appStore';
import { Notify } from 'quasar';

export default route(function (/* { store, ssrContext } */) {
  const createHistory = process.env.SERVER
    ? createMemoryHistory
    : (process.env.VUE_ROUTER_MODE === 'history' ? createWebHistory : createWebHashHistory);

  const Router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(process.env.VUE_ROUTER_BASE),
  });

  // --- GLOBAL NAVIGATION GUARDS ---
  Router.beforeEach((to, from, next) => {
    const appStore = useAppStore();
    
    // 1. Update document title
    const metaTitle = to.meta.title as string || 'Dashboard';
    document.title = `NexusScope — ${metaTitle}`;

    // 2. Update appStore title
    appStore.setPageTitle(metaTitle);

    // 3. API Connection check
    if (to.meta.requiresApi && appStore.apiStatus === 'offline') {
      Notify.create({
        type: 'warning',
        message: 'SYSTEM OFFLINE: OPERATING IN READ-ONLY MODE',
        caption: 'Certain intelligence modules may be unavailable.',
        position: 'top',
        timeout: 3000
      });
    }

    next();
  });

  return Router;
});
