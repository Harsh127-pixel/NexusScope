import { boot } from 'quasar/wrappers';
import { Notify } from 'quasar';

export default boot(({ app }) => {
  app.config.errorHandler = (error: any, instance: any, info: string) => {
    console.error('[NEXUSSCOPE_RUNTIME_FAULT]:', error);
    console.error('[INFO]:', info);
    
    Notify.create({
      type: 'negative',
      message: 'CIRCUIT BREAK: Critical Frontend Runtime Error',
      caption: 'The operation was aborted to prevent data corruption.',
      icon: 'error_outline',
      timeout: 0,
      position: 'bottom-right',
      actions: [{ label: 'RELOAD', color: 'white', handler: () => window.location.reload() }]
    });
  };
});
