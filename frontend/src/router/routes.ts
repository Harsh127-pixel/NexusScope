import { RouteRecordRaw } from 'vue-router';
import DashboardPage from 'pages/DashboardPage.vue';

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    component: () => import('layouts/MainLayout.vue'),
    children: [
      {
        path: '',
        component: DashboardPage,
        meta: { 
          title: 'DASHBOARD', 
          icon: 'LayoutDashboard', 
          requiresApi: true 
        }
      },
      {
        path: 'search',
        component: () => import('pages/SearchPage.vue'),
        meta: { 
          title: 'INTELLIGENCE SEARCH', 
          icon: 'Search', 
          requiresApi: true 
        }
      },
      {
        path: 'results/:taskId',
        component: () => import('pages/ResultsPage.vue'),
        meta: { 
          title: 'INVESTIGATION RESULTS', 
          icon: 'Layers', 
          requiresApi: true 
        },
        beforeEnter: (to, from, next) => {
          const taskId = to.params.taskId as string;
          // UUID v4 format regex
          const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
          
          if (!uuidRegex.test(taskId)) {
            next({ 
              path: '/history', 
              query: { error: 'invalid-task-id' } 
            });
          } else {
            next();
          }
        }
      },
      {
        path: 'history',
        component: () => import('pages/HistoryPage.vue'),
        meta: { 
          title: 'INTELLIGENCE ARCHIVE', 
          icon: 'Clock', 
          requiresApi: true 
        }
      },
      {
        path: 'settings',
        component: () => import('pages/SettingsPage.vue'),
        meta: { 
          title: 'SETTINGS', 
          icon: 'Settings', 
          requiresApi: false 
        }
      },
      {
        path: 'status',
        component: () => import('pages/SystemStatusPage.vue'),
        meta: { 
          title: 'SYSTEM STATUS', 
          icon: 'Activity', 
          requiresApi: true 
        }
      }
    ]
  },

  // 404 NOT FOUND
  {
    path: '/:pathMatch(.*)*',
    component: () => import('pages/NotFoundPage.vue'),
    meta: { 
      title: 'ERROR 404', 
      icon: 'AlertTriangle', 
      requiresApi: false 
    }
  }
];

export default routes;
