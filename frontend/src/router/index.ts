import { route } from 'quasar/wrappers';
import {
  createMemoryHistory,
  createRouter,
  createWebHashHistory,
  createWebHistory,
} from 'vue-router';
import routes from './routes';
import { useAppStore } from 'src/stores/appStore';
import { useAuthStore } from 'src/stores/authStore';
import { Notify } from 'quasar';

export default route(function () {
  const createHistory = process.env.SERVER
    ? createMemoryHistory
    : (process.env.VUE_ROUTER_MODE === 'history' ? createWebHistory : createWebHashHistory);

  const Router = createRouter({
    scrollBehavior: () => ({ left: 0, top: 0 }),
    routes,
    history: createHistory(process.env.VUE_ROUTER_BASE),
  });

  Router.beforeEach(async (to, from, next) => {
    const appStore  = useAppStore();
    const authStore = useAuthStore();

    // 1. Update page title
    document.title = `NexusScope — ${to.meta.title ?? 'Dashboard'}`;
    appStore.setPageTitle(to.meta.title as string ?? 'Dashboard');

    // 2. Wait for auth to initialise (avoids flash redirect on reload)
    if (!authStore.isInitialised) {
      await new Promise<void>(resolve => {
        const stop = authStore.$subscribe(() => {
          if (authStore.isInitialised) { stop(); resolve(); }
        });
        // Safety timeout — if Firebase never fires, proceed after 3s
        setTimeout(resolve, 3000);
      });
    }

    const requiresAuth = to.matched.some(r => r.meta.requiresAuth);
    const isAuthPage   = to.matched.some(r => r.meta.isAuthPage);

    // 3. Redirect unauthenticated users to login
    if (requiresAuth && !authStore.isLoggedIn) {
      return next({ path: '/auth/login', query: { redirect: to.fullPath } });
    }

    // 4. Redirect authenticated users away from login
    if (isAuthPage && authStore.isLoggedIn) {
      return next('/');
    }

    // 5. API connection check warning
    if (to.meta.requiresApi && appStore.apiStatus === 'offline') {
      Notify.create({
        type:     'warning',
        message:  'SYSTEM OFFLINE: OPERATING IN READ-ONLY MODE',
        caption:  'Certain intelligence modules may be unavailable.',
        position: 'top',
        timeout:  3000,
      });
    }

    next();
  });

  return Router;
});
