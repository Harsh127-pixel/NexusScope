<template>
  <q-dialog 
    :model-value="modelValue" 
    @update:model-value="$emit('update:modelValue', $event)"
    persistent
  >
    <q-card class="ns-confirm-card q-pa-lg">
      <div class="row no-wrap items-center q-mb-md">
        <div v-if="danger" class="icon-warning q-mr-md">
          <AlertTriangle :size="32" color="var(--ns-red)" />
        </div>
        <div class="column">
          <div class="ns-label text-muted q-mb-xs">TACTICAL CONFIRMATION</div>
          <div class="ns-heading-sm text-white">{{ title }}</div>
        </div>
      </div>

      <div class="ns-muted q-mb-xl">{{ message }}</div>

      <div class="row justify-end q-gutter-x-md">
        <q-btn flat class="ns-btn-secondary" label="CANCEL" @click="$emit('cancel'); $emit('update:modelValue', false)" />
        <q-btn 
          :color="danger ? 'negative' : 'primary'"
          :label="confirmLabel.toUpperCase()"
          @click="$emit('confirm'); $emit('update:modelValue', false)"
          class="ns-btn-tactical q-px-lg"
        />
      </div>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { AlertTriangle } from 'lucide-vue-next';

interface Props {
  /** Two-way binding for visibility */
  modelValue: boolean;
  /** Primary heading for the dialog */
  title: string;
  /** Detailed warning or descriptive message */
  message: string;
  /** Text for the confirmation button */
  confirmLabel?: string;
  /** If true, uses red theme and shows warning icon for destructive actions */
  danger?: boolean;
}

withDefaults(defineProps<Props>(), {
  confirmLabel: 'Confirm',
  danger: false
});

defineEmits<{
  (e: 'update:modelValue', val: boolean): void;
  (e: 'confirm'): void;
  (e: 'cancel'): void;
}>();
</script>

<style scoped>
.ns-confirm-card {
  background-color: var(--ns-bg-elevated);
  border: 1px solid var(--ns-border);
  border-radius: var(--ns-radius-lg);
  max-width: 440px;
  box-shadow: var(--ns-shadow-lg);
}

.ns-btn-tactical {
  font-family: var(--ns-font-mono);
  letter-spacing: 0.1em;
  font-weight: 600;
}

.icon-warning {
  color: var(--ns-red);
}

.ns-muted {
  color: var(--ns-text-muted);
}
</style>
