<template>
  <div 
    class="ns-task-row row items-center no-wrap q-pa-sm clickable"
    :class="{ 'is-selected': selected }"
    @click="$emit('select')"
  >
    <!-- SELECTOR -->
    <div class="q-mr-md">
      <q-checkbox 
        :model-value="selected" 
        dense 
        color="primary" 
        @update:model-value="$emit('select')" 
      />
    </div>

    <!-- MODULE ICON -->
    <div class="q-mr-md">
      <NsModuleIcon :module="task.module" :size="18" />
    </div>

    <!-- TASK ID -->
    <div class="col-1 text-mono text-caption ns-accent-text q-mr-md">
      {{ task.task_id.substring(0, 8) }}
      <q-tooltip>{{ task.task_id }}</q-tooltip>
    </div>

    <!-- TARGET -->
    <div class="col text-white text-weight-medium ellipsis q-mr-md">
      {{ task.target }}
      <q-tooltip>{{ task.target }}</q-tooltip>
    </div>

    <!-- STATUS -->
    <div class="col-2 q-mr-md">
      <NsStatusBadge :status="task.status" />
    </div>

    <!-- TIME -->
    <div class="col-2 text-caption ns-muted text-right q-mr-md">
      {{ formatTime(task.created_at) }}
    </div>

    <!-- ACTIONS -->
    <div class="actions-overlay row q-gutter-x-xs no-wrap">
      <q-btn flat round dense color="primary" icon="visibility" @click.stop="$emit('view')">
        <q-tooltip>VIEW RESULTS</q-tooltip>
      </q-btn>
      <q-btn flat round dense color="secondary" icon="refresh" @click.stop="$emit('rerun')">
        <q-tooltip>RE-RUN</q-tooltip>
      </q-btn>
      <q-btn flat round dense color="negative" icon="delete" @click.stop="$emit('delete')">
        <q-tooltip>DELETE</q-tooltip>
      </q-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import NsModuleIcon from './NsModuleIcon.vue';
import NsStatusBadge from './NsStatusBadge.vue';
import { Task } from 'src/services/apiService';

interface Props {
  /** The task object to display */
  task: Task;
  /** Whether the row is currently selected for bulk actions */
  selected?: boolean;
}

defineProps<Props>();

const emit = defineEmits<{
  (e: 'view'): void;
  (e: 'rerun'): void;
  (e: 'delete'): void;
  (e: 'select'): void;
}>();

function formatTime(timestamp: string) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
</script>

<style scoped>
.ns-task-row {
  border-bottom: 1px solid var(--ns-border);
  transition: var(--ns-transition);
  height: 52px;
  position: relative;
  background: transparent;
}

.ns-task-row:hover {
  background-color: var(--ns-bg-surface);
}

.ns-task-row.is-selected {
  background-color: var(--ns-accent-dim);
}

.actions-overlay {
  opacity: 0;
  transition: var(--ns-transition);
  background: var(--ns-bg-surface);
  padding-left: 10px;
}

.ns-task-row:hover .actions-overlay {
  opacity: 1;
}

.ns-accent-text {
  color: var(--ns-accent);
}

.ns-muted {
  color: var(--ns-text-muted);
}

.clickable {
  cursor: pointer;
}
</style>
