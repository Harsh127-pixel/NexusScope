<template>
  <div class="ns-data-card q-pa-lg">
    <div class="ns-label text-muted q-mb-xs">{{ label }}</div>
    <div class="row items-baseline no-wrap">
      <div class="ns-heading-lg text-white text-mono">
        {{ currentDisplayValue }}<span v-if="unit" class="text-caption q-ml-xs ns-muted">{{ unit }}</span>
      </div>
      
      <div v-if="trend" :class="['trend-indicator q-ml-md row items-center', `is-${trend}`]">
        <component :is="trend === 'up' ? ChevronUp : ChevronDown" :size="14" />
        <span class="text-caption text-weight-bold">12%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { ChevronUp, ChevronDown } from 'lucide-vue-next';

interface Props {
  /** Descriptive label for the metric */
  label: string;
  /** Numerical or string value to display */
  value: string | number;
  /** Direction of trend */
  trend?: 'up' | 'down' | null;
  /** Optional unit suffix (e.g. 'ms', '%') */
  unit?: string;
}

const props = withDefaults(defineProps<Props>(), {
  trend: null,
  unit: ''
});

const currentDisplayValue = ref<string | number>(0);

onMounted(() => {
  if (typeof props.value === 'number') {
    animateCounter(props.value);
  } else {
    currentDisplayValue.value = props.value;
  }
});

function animateCounter(target: number) {
  const duration = 1000;
  const startTime = performance.now();
  
  function update(currentTime: number) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    
    // Ease out expo
    const easeProgress = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
    
    currentDisplayValue.value = Math.floor(target * easeProgress);
    
    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      currentDisplayValue.value = target;
    }
  }
  
  requestAnimationFrame(update);
}
</script>

<style scoped>
.ns-data-card {
  background-color: var(--ns-bg-surface);
  border-radius: var(--ns-radius-md);
  transition: var(--ns-transition);
  border: 1px solid transparent;
}

.ns-data-card:hover {
  background-color: var(--ns-bg-elevated);
  border-color: var(--ns-border);
}

.trend-indicator {
  padding: 2px 6px;
  border-radius: 4px;
}

.trend-indicator.is-up { color: var(--ns-green); background: rgba(46, 204, 113, 0.1); }
.trend-indicator.is-down { color: var(--ns-red); background: rgba(229, 83, 75, 0.1); }

.ns-muted {
  color: var(--ns-text-muted);
}
</style>
