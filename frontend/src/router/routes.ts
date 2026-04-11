import { RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
  // ── Auth (no layout wrapper) ─────────────────────────────────────────────
  {
    path: '/auth',
    component: () => import('layouts/AuthLayout.vue'),
    children: [
      {
        path: 'login',
        component: () => import('pages/AuthPage.vue'),
        meta: { title: 'SIGN IN', requiresAuth: false, isAuthPage: true },
      },
    ],
  },

  // ── App (requires auth) ──────────────────────────────────────────────────
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        component: () => import('pages/DashboardPage.vue'),
        meta: { title: 'DASHBOARD', icon: 'LayoutDashboard', requiresApi: true },
      },
      {
        path: 'search',
        component: () => import('pages/SearchPage.vue'),
        meta: { title: 'INTELLIGENCE SEARCH', icon: 'Search', requiresApi: true },
      },
      {
        path: 'results/:taskId',
        component: () => import('pages/ResultsPage.vue'),
        meta: { title: 'INVESTIGATION RESULTS', icon: 'Layers', requiresApi: true },
        beforeEnter: (to, from, next) => {
          const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
          if (!uuidRegex.test(to.params.taskId as string)) {
            next({ path: '/history', query: { error: 'invalid-task-id' } });
          } else {
            next();
          }
        },
      },
      {
        path: 'history',
        component: () => import('pages/HistoryPage.vue'),
        meta: { title: 'INTELLIGENCE ARCHIVE', icon: 'Clock', requiresApi: true },
      },
      {
        path: 'settings',
        component: () => import('pages/SettingsPage.vue'),
        meta: { title: 'SETTINGS', icon: 'Settings', requiresApi: false },
      },
      {
        path: 'status',
        component: () => import('pages/SystemStatusPage.vue'),
        meta: { title: 'SYSTEM STATUS', icon: 'Activity', requiresApi: true },
      },
    ],
  },

  // ── 404 ──────────────────────────────────────────────────────────────────
  {
    path: '/:pathMatch(.*)*',
    component: () => import('pages/NotFoundPage.vue'),
    meta: { title: 'ERROR 404', requiresAuth: false },
  },
];

export default routes;
