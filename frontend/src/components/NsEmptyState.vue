<template>
  <div class="ns-empty-state column flex-center q-pa-xl text-center">
    <div class="icon-wrapper q-mb-lg">
      <component :is="iconComponent" :size="48" class="ns-muted" />
    </div>
    
    <h3 class="ns-heading-md text-white q-mt-none q-mb-xs">{{ title }}</h3>
    <p v-if="subtitle" class="ns-muted q-mb-xl">{{ subtitle }}</p>
    
    <q-btn
      v-if="actionLabel"
      color="primary"
      class="ns-btn-tactical q-px-xl"
      :label="actionLabel.toUpperCase()"
      @click="$emit('action')"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { 
  ClipboardList, 
  Search, 
  Layers, 
  Database,
  AlertTriangle,
  FolderOpen
} from 'lucide-vue-next';

interface Props {
  /** Lucide icon name to display */
  icon: 'clipboard' | 'search' | 'layers' | 'database' | 'error' | 'folder';
  /** Primary heading text */
  title: string;
  /** Optional descriptive subtitle */
  subtitle?: string;
  /** Optional button label to trigger an action */
  actionLabel?: string;
}

const props = defineProps<Props>();

defineEmits<{
  (e: 'action'): void;
}>();

const iconComponent = computed(() => {
  switch (props.icon) {
    case 'clipboard': return ClipboardList;
    case 'search': return Search;
    case 'layers': return Layers;
    case 'database': return Database;
    case 'error': return AlertTriangle;
    case 'folder': return FolderOpen;
    default: return Search;
  }
});
</script>

<style scoped>
.ns-empty-state {
  min-height: 300px;
}

.icon-wrapper {
  opacity: 0.3;
}

.ns-btn-tactical {
  font-family: var(--ns-font-mono);
  letter-spacing: 0.1em;
  font-weight: 600;
}

.ns-muted {
  color: var(--ns-text-muted);
}
</style>
