<template>
  <q-card flat class="ns-card-wrapper">
    <div v-if="title" class="ns-card-header row items-center justify-between q-px-lg q-py-md">
      <div class="ns-label text-weight-bold">{{ title }}</div>
      <slot name="header-side"></slot>
    </div>
    <q-separator v-if="title" dark style="opacity: 0.1" />
    <div class="ns-card-body q-pa-lg">
      <slot></slot>
    </div>
  </q-card>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
}>()
</script>

<style scoped>
.ns-card-wrapper {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  border-radius: var(--ns-radius-lg);
  overflow: hidden;
  height: 100%;
}

.ns-card-header {
  background: rgba(255, 255, 255, 0.02);
}

.ns-label {
  color: var(--ns-accent);
  letter-spacing: 0.1em;
  font-size: 11px;
}
</style>
