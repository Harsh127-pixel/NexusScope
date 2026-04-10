<template>
  <q-badge 
    :class="[
      'ns-status-badge', 
      `is-${status}`,
      { 'has-pulse': status === 'processing' }
    ]"
    class="ns-label q-pa-xs no-shadow"
  >
    <div v-if="status === 'processing'" class="pulse-dot q-mr-xs"></div>
    <span class="badge-text">{{ status.toUpperCase() }}</span>
  </q-badge>
</template>

<script setup lang="ts">
/**
 * @typedef {'queued'|'processing'|'completed'|'failed'|'active'|'offline'} StatusType
 */

interface Props {
  /** The current status of the task or system */
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'active' | 'offline';
}

defineProps<Props>();
</script>

<style scoped>
.ns-status-badge {
  background-color: var(--ns-bg-elevated);
  border: 1px solid var(--ns-border);
  color: var(--ns-text-primary);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  border-radius: var(--ns-radius-sm);
  display: inline-flex;
  align-items: center;
}

.is-queued { color: var(--ns-amber); border-color: rgba(245, 166, 35, 0.3); }
.is-processing { color: var(--ns-blue); border-color: rgba(52, 152, 219, 0.3); }
.is-completed { color: var(--ns-green); border-color: rgba(46, 204, 113, 0.3); }
.is-failed { color: var(--ns-red); border-color: rgba(229, 83, 75, 0.3); }
.is-active { color: var(--ns-accent); border-color: var(--ns-accent-dim); }
.is-offline { color: var(--ns-text-muted); border-color: var(--ns-border); }

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: currentColor;
}

.has-pulse .pulse-dot {
  animation: pulse-kf 1.5s infinite;
}

@keyframes pulse-kf {
  0% { transform: scale(0.95); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.5; }
  100% { transform: scale(0.95); opacity: 1; }
}

.badge-text {
  font-family: var(--ns-font-mono);
}
</style>
