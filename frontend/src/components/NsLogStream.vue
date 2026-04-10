<template>
  <div class="ns-log-stream column no-wrap bg-black q-pa-md rounded-borders border-ns shadow-24">
    <div class="scroll-container col" ref="scrollArea">
      <div v-for="(log, index) in logs" :key="index" class="log-line text-mono">
        <span class="log-prefix">>>> </span>
        <span class="log-content">{{ log }}</span>
      </div>
      
      <!-- STATUS LINE -->
      <div v-if="logs.length > 0 && !isRunning" class="q-mt-sm">
        <div v-if="isSuccess" class="text-green text-mono text-weight-bold">
          [ PROCESS_COMPLETE : SIGNAL_STABLE ]
        </div>
        <div v-else class="text-red text-mono text-weight-bold">
          [ PROCESS_FAILED : CONNECTION_TERMINATED ]
        </div>
      </div>

      <!-- CURSOR -->
      <div v-if="isRunning" class="cursor-line text-mono text-primary row items-center">
        <span class="log-prefix">>>> </span>
        <div class="blinking-cursor q-ml-xs"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

interface Props {
  /** Array of log messages to stream */
  logs: string[];
  /** Whether the process is currently running and should show a cursor */
  isRunning: boolean;
  /** Whether the final state was a success (affects color of final line) */
  isSuccess?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  isSuccess: true
});

const scrollArea = ref<HTMLElement | null>(null);

watch(() => props.logs.length, () => {
  nextTick(() => {
    if (scrollArea.value) {
      scrollArea.value.scrollTop = scrollArea.value.scrollHeight;
    }
  });
});
</script>

<style scoped>
.ns-log-stream {
  height: 300px;
  border: 1px solid var(--ns-border);
  position: relative;
}

.scroll-container {
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--ns-border) transparent;
}

.log-line {
  line-height: 1.5;
  font-size: 12px;
  color: var(--ns-text-secondary);
  word-break: break-all;
}

.log-prefix {
  color: var(--ns-accent);
  opacity: 0.5;
}

.blinking-cursor {
  width: 8px;
  height: 14px;
  background-color: var(--ns-accent);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  from, to { opacity: 1; }
  50% { opacity: 0; }
}

.border-ns {
  border-color: var(--ns-border);
}

.text-green { color: var(--ns-green); }
.text-red { color: var(--ns-red); }
</style>
