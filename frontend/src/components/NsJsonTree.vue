<template>
  <div class="ns-json-tree q-ml-md" :class="{ 'is-root': !depth }">
    <div v-for="(value, key) in data" :key="key" class="ns-json-row">
      <!-- OBJECTS AND ARRAYS -->
      <div v-if="isObject(value) && value !== null" class="ns-json-collapsible">
        <div 
          class="row items-center cursor-pointer ns-json-key-wrapper" 
          @click="toggle(key)"
        >
          <ChevronRight 
            :size="14" 
            :class="['q-mr-xs transition-300', { 'rotate-90': expanded[key] }]" 
            class="ns-muted"
          />
          <span class="ns-json-key text-mono">{{ key }}:</span>
          <span class="ns-muted q-ml-xs text-caption">
            {{ isArray(value) ? `Array(${value.length})` : 'Object' }}
          </q-badge>
        </div>
        
        <q-slide-transition>
          <div v-show="expanded[key]">
            <NsJsonTree :data="value" :depth="(depth || 0) + 1" />
          </div>
        </q-slide-transition>
      </div>

      <!-- PRIMITIVES -->
      <div v-else class="row items-center ns-json-primitive no-wrap">
        <span class="ns-json-key text-mono q-mr-xs">{{ key }}:</span>
        <span 
          :class="['ns-json-value text-mono cursor-pointer', getValueClass(value)]"
          @click="copyValue(value, $event)"
        >
          {{ formatValue(value) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';
import { ChevronRight } from 'lucide-vue-next';
import { copyToClipboard, Notify } from 'quasar';

interface Props {
  /** The data object to render */
  data: Record<string, any> | any[];
  /** Internal depth counter for recursion */
  depth?: number;
}

const props = withDefaults(defineProps<Props>(), {
  depth: 0
});

const expanded = reactive<Record<string, boolean>>({});

function isObject(v: any) {
  return typeof v === 'object' && v !== null;
}

function isArray(v: any) {
  return Array.isArray(v);
}

function toggle(key: string | number) {
  expanded[key] = !expanded[key];
}

function getValueClass(v: any) {
  if (v === null) return 'is-null';
  if (typeof v === 'string') return 'is-string';
  if (typeof v === 'number') return 'is-number';
  if (typeof v === 'boolean') return 'is-boolean';
  return '';
}

function formatValue(v: any) {
  if (v === null) return 'null';
  if (typeof v === 'string') return `"${v}"`;
  return String(v);
}

function copyValue(v: any, event: MouseEvent) {
  const el = event.currentTarget as HTMLElement;
  copyToClipboard(String(v)).then(() => {
    el.classList.add('flash-indicator');
    setTimeout(() => el.classList.remove('flash-indicator'), 300);
    Notify.create({ message: 'Copied to clipboard', color: 'primary', position: 'bottom', timeout: 1000 });
  });
}
</script>

<style scoped>
.ns-json-tree {
  border-left: 1px solid var(--ns-border);
  font-size: 13px;
}

.ns-json-tree.is-root {
  margin-left: 0;
  border-left: none;
}

.ns-json-row {
  padding: 2px 0;
}

.ns-json-key {
  color: var(--ns-text-muted);
  font-weight: 500;
}

.ns-json-value {
  padding: 0 4px;
  border-radius: 2px;
  transition: background 0.2s;
}

.ns-json-value:hover {
  background: var(--ns-accent-dim);
}

.is-string { color: var(--ns-text-primary); }
.is-number { color: var(--ns-amber); }
.is-boolean { color: var(--ns-accent); }
.is-null { color: var(--ns-text-muted); font-style: italic; }

.flash-indicator {
  background: var(--ns-accent) !important;
  color: black !important;
}

.transition-300 { transition: transform 0.3s; }
.rotate-90 { transform: rotate(90deg); }
.ns-muted { color: var(--ns-text-muted); }
</style>
