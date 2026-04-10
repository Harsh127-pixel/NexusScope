import { useQuasar } from 'quasar';
import { useRouter } from 'vue-router';

export function useNotify() {
  const $q = useQuasar();
  const router = useRouter();

  const notifySuccess = (message: string) => {
    $q.notify({
      type: 'positive',
      message,
      icon: 'check_circle',
      color: 'green-7',
      position: 'bottom-right'
    });
  };

  const notifyError = (message: string) => {
    $q.notify({
      type: 'negative',
      message,
      icon: 'report_problem',
      color: 'red-7',
      position: 'bottom-right'
    });
  };

  const notifyWarning = (message: string) => {
    $q.notify({
      type: 'warning',
      message,
      icon: 'warning',
      color: 'amber-8',
      textColor: 'black',
      position: 'bottom-right'
    });
  };

  const notifyInfo = (message: string) => {
    $q.notify({
      type: 'info',
      message,
      icon: 'info',
      color: 'indigo-7',
      position: 'bottom-right'
    });
  };

  const notifyTaskComplete = (taskId: string) => {
    $q.notify({
      message: `TACTICAL INVESTIGATION COMPLETE: ${taskId.substring(0, 8)}`,
      caption: 'Click to analyze captured intelligence data.',
      icon: 'radar',
      color: 'indigo-10',
      textColor: 'primary',
      position: 'bottom-right',
      actions: [
        { 
          label: 'VIEW RESULTS', 
          color: 'primary', 
          handler: () => { router.push(`/results/${taskId}`) } 
        }
      ]
    });
  };

  return {
    notifySuccess,
    notifyError,
    notifyWarning,
    notifyInfo,
    notifyTaskComplete
  };
}
