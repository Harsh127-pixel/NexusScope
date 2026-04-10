import { ref, onUnmounted } from 'vue';

/**
 * Generic tactical polling hook
 * @param fn Async function that returns true when polling should stop
 * @param intervalMs Delay between polls
 */
export function usePoll(fn: () => Promise<boolean>, intervalMs: number = 2000) {
  const isPolling = ref(false);
  const pollCount = ref(0);
  const pollTimeout = ref<any>(null);

  const start = async () => {
    if (isPolling.value) return;
    isPolling.value = true;
    pollCount.value = 0;
    executePoll();
  };

  const stop = () => {
    isPolling.value = false;
    if (pollTimeout.value) {
      clearTimeout(pollTimeout.value);
      pollTimeout.value = null;
    }
  };

  const executePoll = async () => {
    if (!isPolling.value) return;

    try {
      const shouldStop = await fn();
      pollCount.value++;
      
      if (shouldStop) {
        stop();
      } else {
        pollTimeout.value = setTimeout(executePoll, intervalMs);
      }
    } catch (error) {
      console.error('POLL_STALL: Retrying connection...', error);
      pollTimeout.value = setTimeout(executePoll, intervalMs);
    }
  };

  onUnmounted(() => {
    stop();
  });

  return {
    start,
    stop,
    isPolling,
    pollCount
  };
}
