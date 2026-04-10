<template>
  <div class="ns-module-icon-wrapper row items-center no-wrap">
    <div 
      class="icon-container flex flex-center"
      :style="{ width: `${size + 12}px`, height: `${size + 12}px` }"
    >
      <component 
        :is="iconComponent" 
        :size="size" 
        class="module-icon"
      />
    </div>
    <span v-if="showLabel" class="ns-label q-ml-sm">{{ module.toUpperCase() }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { 
  User, 
  Globe, 
  MapPin, 
  FileSearch, 
  Navigation, 
  Code,
  Activity
} from 'lucide-vue-next';

interface Props {
  /** OSINT Module type */
  module: 'username' | 'domain' | 'ip' | 'metadata' | 'geolocation' | 'scraper';
  /** Icon size in pixels */
  size?: number;
  /** Whether to show the module label text */
  showLabel?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  size: 24,
  showLabel: false
});

const iconComponent = computed(() => {
  switch (props.module) {
    case 'username': return User;
    case 'domain': return Globe;
    case 'ip': return MapPin;
    case 'metadata': return FileSearch;
    case 'geolocation': return Navigation;
    case 'scraper': return Code;
    default: return Activity;
  }
});
</script>

<style scoped>
.icon-container {
  background-color: var(--ns-accent-dim);
  border-radius: var(--ns-radius-sm);
  color: var(--ns-accent);
  transition: var(--ns-transition);
}

.module-icon {
  stroke-width: 2;
}

.ns-label {
  font-family: var(--ns-font-mono);
  font-size: 11px;
  letter-spacing: 0.05em;
  color: var(--ns-text-secondary);
}
</style>
