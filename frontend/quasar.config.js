const { configure } = require('quasar/wrappers');
const path = require('path');

module.exports = configure(function (ctx) {
  return {
    boot: [
      'axios',
      'error-handler'
    ],

    css: [
      'variables.css',
      'typography.css',
      'quasar-overrides.css',
      'animations.css'
    ],

    extras: [
      'material-icons',
    ],

    build: {
      target: {
        browser: ['es2020', 'edge88', 'firefox78', 'chrome87', 'safari13.1'],
        node: 'node16'
      },

      vueRouterMode: 'history',

      alias: {
        'src': path.join(__dirname, 'src'),
        'components': path.join(__dirname, 'src/components'),
        'layouts': path.join(__dirname, 'src/layouts'),
        'pages': path.join(__dirname, 'src/pages'),
        'assets': path.join(__dirname, 'src/assets'),
        'boot': path.join(__dirname, 'src/boot'),
        'stores': path.join(__dirname, 'src/stores'),
        'services': path.join(__dirname, 'src/services'),
        'composables': path.join(__dirname, 'src/composables')
      },

      // Use vite compression
      vitePlugins: [
        ['vite-plugin-compression', { algorithm: 'gzip' }]
      ],

      // Rollup optimizations
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('lucide')) return 'vendor-icons';
              if (id.includes('leaflet')) return 'vendor-maps';
              if (id.includes('vue-json-pretty')) return 'vendor-viz';
              return 'vendor';
            }
          }
        }
      }
    },

    devServer: {
      port: 9000,
      open: true
    },

    framework: {
      config: {
        dark: true,
        brand: {
          primary: '#00D4AA',
          secondary: '#1A2332',
          accent: '#00D4AA', // Aligning with design system
          dark: '#0D1117',
          positive: '#2ECC71',
          negative: '#E5534B',
          info: '#3498DB',
          warning: '#F5A623'
        }
      },
      plugins: [
        'Notify',
        'Dialog',
        'Loading'
      ]
    },

    animations: [],

    ssr: {
      pwa: false,
    },

    pwa: {
      workboxMode: 'generateSW',
      injectPwaMetaTag: true,
      swFilename: 'sw.js',
      manifest: {
        name: 'NexusScope',
        short_name: 'NexusScope',
        description: 'OSINT Digital Intelligence Aggregation Platform',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#0D1117',
        theme_color: '#00D4AA'
      }
    }
  }
});
