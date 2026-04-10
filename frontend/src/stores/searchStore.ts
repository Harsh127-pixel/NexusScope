import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import { apiService, Module } from 'src/services/apiService';
import { useAppStore } from './appStore';

export type Theater = 'darkweb' | 'recon' | 'identity' | 'classic';

export interface ModuleOption {
  label: string;
  value: Module;
  theater: Theater;
  description: string;
  placeholder: string;
}

export const MODULE_OPTIONS: ModuleOption[] = [
  // ── Theater 1: Dark Web / Onion ──────────────────────────────
  {
    label: 'ONION CRAWLER',
    value: 'darkweb',
    theater: 'darkweb',
    description: 'Crawl .onion hidden services via Tor SOCKS5 proxy',
    placeholder: 'http://example.onion or paste onion URL',
  },
  // ── Theater 2: General Recon & Footprinting ───────────────────
  {
    label: 'DOMAIN ANALYSIS',
    value: 'domain',
    theater: 'recon',
    description: 'DNS records, WHOIS, subdomains, TLS, trust score',
    placeholder: 'example.com',
  },
  {
    label: 'IP INTELLIGENCE',
    value: 'ip',
    theater: 'recon',
    description: 'Geolocation, ASN, ISP, PTR records',
    placeholder: '1.1.1.1 or 2001:4860:4860::8888',
  },
  {
    label: 'WEB SCRAPER',
    value: 'scraper',
    theater: 'recon',
    description: 'Full-page scrape — title, links, meta, h1 extraction',
    placeholder: 'https://example.com',
  },
  {
    label: 'PHONE LOOKUP',
    value: 'phone',
    theater: 'recon',
    description: 'Carrier, line type, country — Skip Tracer equivalent',
    placeholder: '+1-555-867-5309',
  },
  // ── Theater 3: Identity & Credential Hunting ─────────────────
  {
    label: 'EMAIL HUNT',
    value: 'email',
    theater: 'identity',
    description: 'Gravatar profile + HaveIBeenPwned breach lookup',
    placeholder: 'target@example.com',
  },
  {
    label: 'USERNAME RECON',
    value: 'username',
    theater: 'identity',
    description: 'Multi-platform: GitHub, Reddit, HackerNews, Twitter/X',
    placeholder: 'username_to_search',
  },
  // ── Classic ───────────────────────────────────────────────────
  {
    label: 'METADATA EXTRACTION',
    value: 'metadata',
    theater: 'classic',
    description: 'EXIF metadata from image URL',
    placeholder: 'https://example.com/photo.jpg',
  },
  {
    label: 'GEOLOCATION',
    value: 'geolocation',
    theater: 'classic',
    description: 'Coordinate and location mapping',
    placeholder: '40.7128,-74.0060',
  },
];

export const useSearchStore = defineStore('search', () => {
  const appStore = useAppStore();

  // --- STATE ---
  const selectedModule = ref<Module>('domain');
  const selectedTheater = ref<Theater>('recon');
  const targetInput = ref('');
  const isDispatching = ref(false);
  const lastError = ref<string | null>(null);
  const lastTaskId = ref<string | null>(null);

  // Legacy compat: flat list for select dropdowns
  const moduleOptions = MODULE_OPTIONS.map(m => ({ label: m.label, value: m.value }));

  // --- GETTERS ---
  const currentModuleOption = computed(() =>
    MODULE_OPTIONS.find(m => m.value === selectedModule.value) ?? MODULE_OPTIONS[0]
  );

  const theaterModules = computed(() =>
    MODULE_OPTIONS.filter(m => m.theater === selectedTheater.value)
  );

  const inputPlaceholder = computed(() => currentModuleOption.value.placeholder);

  // --- ACTIONS ---
  function setModule(module: Module) {
    selectedModule.value = module;
    const opt = MODULE_OPTIONS.find(m => m.value === module);
    if (opt) selectedTheater.value = opt.theater;
  }

  function setTheater(theater: Theater) {
    selectedTheater.value = theater;
    // Auto-select first module of that theater
    const first = MODULE_OPTIONS.find(m => m.theater === theater);
    if (first) selectedModule.value = first.value;
  }

  function updateTarget(value: string) {
    targetInput.value = value;
  }

  async function dispatchQuery(options: Record<string, any> = {}) {
    isDispatching.value = true;
    lastError.value = null;
    try {
      const response = await apiService.createTask(selectedModule.value, targetInput.value, options);
      lastTaskId.value = response.task_id;
      appStore.incrementActiveTaskCount();
      return response.task_id;
    } catch (error: any) {
      lastError.value = error.response?.data?.message || 'FAILED TO INITIATE TACTICAL QUERY';
      throw error;
    } finally {
      isDispatching.value = false;
    }
  }

  function clearError() {
    lastError.value = null;
  }

  return {
    selectedModule,
    selectedTheater,
    targetInput,
    moduleOptions,
    MODULE_OPTIONS,
    isDispatching,
    lastError,
    lastTaskId,
    currentModuleOption,
    theaterModules,
    inputPlaceholder,
    setModule,
    setTheater,
    updateTarget,
    dispatchQuery,
    clearError,
  };
});
