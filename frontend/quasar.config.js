const { configure } = require('quasar/wrappers');

module.exports = configure(function (/* ctx */) {
  return {
    boot: [],
    css: ['app.css'],
    extras: [
      'roboto-font',
      'material-icons'
    ],
    build: {
      target: {
        browser: ['es2019', 'edge88', 'firefox78', 'chrome87', 'safari13.1'],
        node: 'node16'
      },
      vueRouterMode: 'history',
    },
    devServer: {
      open: true,
      port: 9000
    },
    framework: {
      config: {
        dark: true
      },
      plugins: ['Notify', 'Loading', 'Dialog']
    },
    animations: [],
    ssr: { pwa: false },
    pwa: { workboxMode: 'generateSW' },
    cordova: {},
    capacitor: {},
    electron: {},
    bex: {}
  }
});
