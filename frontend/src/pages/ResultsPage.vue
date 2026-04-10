<template>
  <q-page :class="$q.screen.gt.sm ? 'q-pa-xl' : 'q-pa-md'">
    <!-- TASK HEADER -->
    <div class="row items-center justify-between q-mb-xl">
      <div class="column">
        <q-breadcrumbs class="ns-label q-mb-sm" active-color="primary">
          <q-breadcrumbs-el label="DASHBOARD" to="/" />
          <q-breadcrumbs-el label="SEARCH" to="/search" />
          <q-breadcrumbs-el label="RESULTS" />
        </q-breadcrumbs>
        
        <div class="row items-center q-gutter-x-md">
          <div 
            class="ns-heading-md text-white cursor-pointer hover-accent" 
            @click="copyTaskId"
          >
            {{ taskId }}
            <q-tooltip>CLICK TO COPY TASK ID</q-tooltip>
          </div>
          <q-badge :color="getModuleColor" class="ns-label q-pa-sm">
            {{ currentTask?.module || 'MODULE_UNKNOWN' }}
          </q-badge>
          <div class="row items-center ns-muted text-mono text-caption">
            <Target :size="14" class="q-mr-xs" />
            {{ currentTask?.target || 'TARGETING...' }}
          </div>
          <q-badge 
            :color="getStatusColor" 
            :class="{ 'animate-pulse': currentTask?.status === 'processing' }"
            class="ns-label"
          >
            {{ currentTask?.status?.toUpperCase() || 'INITIALIZING' }}
          </q-badge>
        </div>
      </div>

      <div class="row q-gutter-x-sm" v-if="currentTask?.status === 'completed'">
        <q-btn flat class="ns-btn-secondary" icon="print" label="PRINT REPORT" @click="printReport" />
        <q-btn flat class="ns-btn-secondary" icon="download" label="EXPORT JSON" @click="exportJson" />
        <q-btn flat class="ns-btn-secondary" icon="content_copy" label="COPY RAW" @click="copyRaw" />
        <q-btn color="primary" icon="add" label="NEW SEARCH" to="/search" />
      </div>
    </div>

    <!-- POLLING / LOADING STATE -->
    <div v-if="resultsStore.isPolling" class="column flex-center q-py-xl">
      <q-linear-progress indeterminate color="primary" class="q-mb-xl" />
      
      <q-card flat class="ns-polling-card q-pa-xl">
        <div class="text-center">
          <component 
            :is="getActiveModuleIcon" 
            :size="64" 
            class="ns-accent-text q-mb-lg animate-bounce" 
          />
          <h2 class="ns-heading-md text-white q-mb-md">Analyzing Target Environment...</h2>
        </div>

        <div class="ns-terminal-output q-mt-xl bg-black q-pa-md rounded-borders border-ns">
          <div 
            v-for="(log, index) in resultsStore.logs" 
            :key="index" 
            class="text-mono text-caption q-mb-xs"
          >
            {{ log }}
          </div>
          <div class="text-blue animate-pulse q-mt-sm">[_] Awaiting synchronization...</div>
        </div>
      </q-card>
    </div>

    <!-- RESULTS DISPLAY -->
    <div v-if="currentTask?.status === 'completed'" class="ns-results-container">
      <section v-if="isDomainTask" class="ns-report-card q-pa-xl q-mb-xl ns-print-only-domain-report">
        <div class="row items-start justify-between q-mb-lg">
          <div>
            <div class="ns-label q-mb-xs">DOMAIN INVESTIGATION REPORT</div>
            <h2 class="ns-heading-lg text-white q-ma-none">{{ currentTask?.target }}</h2>
            <div class="ns-muted text-mono q-mt-sm">Generated for DNS parameter review and print output.</div>
          </div>
          <div class="column items-end q-gutter-y-xs">
            <q-badge color="primary" class="ns-label">{{ currentTask?.module?.toUpperCase() }}</q-badge>
            <div class="ns-muted text-mono text-caption">TASK ID: {{ taskId }}</div>
            <div class="ns-muted text-mono text-caption">STATUS: {{ currentTask?.status?.toUpperCase() }}</div>
          </div>
        </div>

        <div class="row q-col-gutter-md q-mb-lg">
          <div class="col-12 col-md-4" v-for="item in domainSummaryCards" :key="item.label">
            <q-card flat class="ns-summary-cell q-pa-md">
              <div class="ns-label text-muted q-mb-xs">{{ item.label }}</div>
              <div class="text-mono text-weight-bold text-white ellipsis">{{ item.value }}</div>
            </q-card>
          </div>
        </div>

        <div class="q-mb-lg">
          <div class="ns-label q-mb-sm">DNS PARAMETERS</div>
          <div class="row q-col-gutter-md">
            <div class="col-12 col-md-6" v-for="entry in dnsParameterEntries" :key="entry.type">
              <q-card flat class="ns-report-block q-pa-md">
                <div class="row items-center justify-between q-mb-sm">
                  <div class="ns-label">{{ entry.type }}</div>
                  <q-badge color="secondary" class="ns-label">{{ entry.count }} RECORDS</q-badge>
                </div>
                <div v-if="entry.values.length" class="column q-gutter-y-xs">
                  <div v-for="(value, index) in entry.values" :key="index" class="ns-code ns-report-value">
                    {{ value }}
                  </div>
                </div>
                <div v-else class="ns-muted text-caption text-mono">NO VALUES RETURNED</div>
              </q-card>
            </div>
          </div>
        </div>

        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">TARGET PARAMETERS</div>
              <div class="column q-gutter-y-sm text-mono">
                <div><span class="ns-muted">DOMAIN:</span> {{ currentTask?.target }}</div>
                <div><span class="ns-muted">SOURCE:</span> {{ domainResult?.source || 'dns_asyncresolver' }}</div>
                <div><span class="ns-muted">TOTAL RECORD TYPES:</span> {{ dnsParameterEntries.length }}</div>
              </div>
            </q-card>
          </div>
          <div class="col-12 col-md-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">TASK DETAILS</div>
              <div class="column q-gutter-y-sm text-mono">
                <div><span class="ns-muted">TASK ID:</span> {{ taskId }}</div>
                <div><span class="ns-muted">STATUS:</span> {{ currentTask?.status }}</div>
                <div><span class="ns-muted">MODULE:</span> {{ currentTask?.module }}</div>
              </div>
            </q-card>
          </div>
        </div>

        <div class="row q-col-gutter-md q-mb-lg">
          <div class="col-12 col-md-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">WHOIS INFORMATION</div>
              <div class="column q-gutter-y-sm text-mono ns-report-kv">
                <div><span class="ns-muted">REGISTRAR:</span> {{ domainResult?.whois?.registrar || 'N/A' }}</div>
                <div><span class="ns-muted">CREATED:</span> {{ formatDomainDate(domainResult?.whois?.creation_date) }}</div>
                <div><span class="ns-muted">UPDATED:</span> {{ formatDomainDate(domainResult?.whois?.updated_date) }}</div>
                <div><span class="ns-muted">EXPIRES:</span> {{ formatDomainDate(domainResult?.whois?.expiration_date) }}</div>
                <div><span class="ns-muted">WHOIS SERVER:</span> {{ domainResult?.whois?.whois_server || 'N/A' }}</div>
                <div><span class="ns-muted">REGISTRANT REGION:</span> {{ [domainResult?.whois?.registrant_state, domainResult?.whois?.registrant_country].filter(Boolean).join(', ') || 'N/A' }}</div>
              </div>
            </q-card>
          </div>

          <div class="col-12 col-md-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">WEB FINGERPRINT</div>
              <div class="column q-gutter-y-sm text-mono ns-report-kv">
                <div><span class="ns-muted">URL:</span> {{ domainResult?.web?.url || 'N/A' }}</div>
                <div><span class="ns-muted">STATUS CODE:</span> {{ domainResult?.web?.status_code || 'N/A' }}</div>
                <div><span class="ns-muted">SERVER:</span> {{ domainResult?.web?.server || 'N/A' }}</div>
                <div><span class="ns-muted">TITLE:</span> {{ domainResult?.web?.title || 'N/A' }}</div>
                <div><span class="ns-muted">X-POWERED-BY:</span> {{ domainResult?.web?.x_powered_by || 'N/A' }}</div>
              </div>
            </q-card>
          </div>
        </div>

        <div class="row q-col-gutter-md q-mb-lg">
          <div class="col-12 col-md-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">SUBDOMAIN ENUMERATION</div>
              <div class="column q-gutter-y-xs">
                <div v-for="entry in domainResult?.subdomains || []" :key="entry.subdomain" class="ns-code ns-report-value">
                  {{ entry.subdomain }}<span v-if="entry.ips?.length"> - {{ entry.ips.join(', ') }}</span>
                </div>
                <div v-if="!(domainResult?.subdomains || []).length" class="ns-muted text-caption text-mono">NO SUBDOMAINS DISCOVERED</div>
              </div>
            </q-card>
          </div>

          <div class="col-12 col-md-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">TLS / CERTIFICATE METADATA</div>
              <div class="column q-gutter-y-sm text-mono ns-report-kv">
                <div><span class="ns-muted">ISSUER:</span> {{ domainResult?.tls?.issuer || 'N/A' }}</div>
                <div><span class="ns-muted">SUBJECT:</span> {{ domainResult?.tls?.subject || 'N/A' }}</div>
                <div><span class="ns-muted">VALID FROM:</span> {{ domainResult?.tls?.not_before || 'N/A' }}</div>
                <div><span class="ns-muted">VALID TO:</span> {{ domainResult?.tls?.not_after || 'N/A' }}</div>
                <div><span class="ns-muted">TLS VERSION:</span> {{ domainResult?.tls?.tls_version || 'N/A' }}</div>
              </div>
            </q-card>
          </div>
        </div>

        <div class="row q-col-gutter-md q-mb-lg">
            <div class="col-12 col-md-6">
              <q-card flat class="ns-report-block q-pa-md">
                <div class="ns-label q-mb-sm">AWS S3 BUCKET SCAN</div>
                <div class="column q-gutter-y-sm text-mono ns-report-kv">
                  <div><span class="ns-muted">BASE NAME:</span> {{ domainResult?.s3_buckets?.base_name || 'N/A' }}</div>
                  <div><span class="ns-muted">CHECKED:</span> {{ domainResult?.s3_buckets?.total_checked || 0 }} permutations</div>
                  <div><span class="ns-muted">VULNERABLE:</span> <span class="text-negative">{{ domainResult?.s3_buckets?.vulnerable_count || 0 }}</span></div>
                  <div><span class="ns-muted">SECURE:</span> <span class="text-positive">{{ domainResult?.s3_buckets?.secure_count || 0 }}</span></div>
                </div>
              </q-card>
            </div>
          </div>

          <div v-if="domainResult?.s3_buckets?.vulnerable_buckets?.length || domainResult?.s3_buckets?.secure_buckets?.length" class="row q-col-gutter-md q-mb-lg">
            <div v-if="domainResult?.s3_buckets?.vulnerable_buckets?.length" class="col-12 col-md-6">
              <q-card flat class="ns-report-block q-pa-md" style="border-left: 3px solid #f44336;">
                <div class="ns-label q-mb-sm text-negative">VULNERABLE S3 BUCKETS (200 OK)</div>
                <div class="column q-gutter-y-xs">
                  <div v-for="bucket in domainResult.s3_buckets.vulnerable_buckets" :key="bucket" class="ns-code ns-report-value text-negative">
                    {{ bucket }}.s3.amazonaws.com
                  </div>
                  <div class="ns-muted text-caption q-mt-sm">⚠️ These buckets allow public access. Verify bucket policies and ACLs immediately.</div>
                </div>
              </q-card>
            </div>

            <div v-if="domainResult?.s3_buckets?.secure_buckets?.length" class="col-12 col-md-6">
              <q-card flat class="ns-report-block q-pa-md" style="border-left: 3px solid #4caf50;">
                <div class="ns-label q-mb-sm text-positive">SECURE S3 BUCKETS (403 Forbidden)</div>
                <div class="column q-gutter-y-xs">
                  <div v-for="bucket in domainResult.s3_buckets.secure_buckets" :key="bucket" class="ns-code ns-report-value text-positive">
                    {{ bucket }}.s3.amazonaws.com
                  </div>
                  <div class="ns-muted text-caption q-mt-sm">✓ These buckets are access-restricted. No public read/write vulnerability detected.</div>
                </div>
              </q-card>
            </div>
          </div>

          <div v-if="!domainResult?.s3_buckets?.vulnerable_buckets?.length && !domainResult?.s3_buckets?.secure_buckets?.length && domainResult?.s3_buckets" class="row q-col-gutter-md q-mb-lg">
            <div class="col-12">
              <q-card flat class="ns-report-block q-pa-md">
                <div class="ns-label q-mb-sm">AWS S3 BUCKET SCAN RESULTS</div>
                <div class="ns-muted text-mono text-caption">No S3 buckets found for this domain. Scanned {{ domainResult?.s3_buckets?.total_checked || 0 }} common permutations.</div>
              </q-card>
            </div>
          </div>

          <div class="row q-col-gutter-md q-mb-lg">
          <div class="col-12 col-md-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">PUBLIC REPUTATION / HISTORY SIGNALS</div>
              <div class="column q-gutter-y-xs text-mono ns-report-kv">
                <div v-if="domainResult?.web?.robots_txt"><span class="ns-muted">ROBOTS.TXT:</span> present</div>
                <div v-if="domainResult?.web?.sitemap_xml"><span class="ns-muted">SITEMAP.XML:</span> present</div>
                <div><span class="ns-muted">SUBDOMAIN COUNT:</span> {{ domainResult?.subdomains?.length || 0 }}</div>
                <div><span class="ns-muted">SAN COUNT:</span> {{ domainResult?.tls?.san?.length || 0 }}</div>
                <div class="ns-muted text-caption">Public reputation is inferred from technical signals, not third-party review databases.</div>
              </div>
            </q-card>
          </div>

          <div class="col-12 col-md-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">TRUST SCORE</div>
              <div class="column q-gutter-y-sm">
                <div class="row items-center justify-between text-mono">
                  <span class="ns-muted">SCORE</span>
                  <span class="text-white text-weight-bold">{{ domainResult?.trust?.score ?? 'N/A' }}/100</span>
                </div>
                <q-linear-progress
                  :value="(domainResult?.trust?.score || 0) / 100"
                  color="primary"
                  size="12px"
                  class="rounded-borders ns-progress-bg"
                />
                <div class="text-mono ns-muted">RATING: {{ (domainResult?.trust?.rating || 'unknown').toUpperCase() }}</div>
                <div v-if="domainResult?.trust?.signals?.length" class="column q-gutter-y-xs">
                  <div v-for="signal in domainResult.trust.signals" :key="signal" class="ns-code ns-report-value">+ {{ signal }}</div>
                </div>
                <div v-if="domainResult?.trust?.warnings?.length" class="column q-gutter-y-xs q-mt-sm">
                  <div v-for="warning in domainResult.trust.warnings" :key="warning" class="ns-muted text-caption">- {{ warning }}</div>
                </div>
              </div>
            </q-card>
          </div>
        </div>
      </section>

      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- THEATER 1: DARK WEB / ONION CRAWLER RESULTS               -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      <section v-if="currentTask?.module === 'darkweb'" class="ns-report-card q-pa-xl q-mb-xl" style="border-color: rgba(139,92,246,0.4)">
        <div class="row items-center q-gutter-x-sm q-mb-lg">
          <Eye :size="24" style="color:#a855f7" />
          <div>
            <div class="ns-label" style="color:#a855f7">THEATER I — DARK WEB / ONION CRAWLER</div>
            <h2 class="ns-heading-md text-white q-ma-none">{{ currentTask?.target }}</h2>
          </div>
        </div>

        <!-- Tor Status -->
        <div class="row q-col-gutter-md q-mb-lg">
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">TOR STATUS</div>
              <div class="column q-gutter-y-xs text-mono">
                <div>
                  <span class="ns-muted">PROXY:</span>
                  {{ currentTask?.result?.tor_status?.proxy_url || 'N/A' }}
                </div>
                <div>
                  <span class="ns-muted">TOR ACTIVE:</span>
                  <span :class="currentTask?.result?.tor_status?.tor_running ? 'text-positive' : 'text-warning'">
                    {{ currentTask?.result?.tor_status?.tor_running ? 'YES' : 'NO' }}
                  </span>
                </div>
                <div v-if="currentTask?.result?.tor_status?.exit_ip">
                  <span class="ns-muted">EXIT NODE IP:</span>
                  {{ currentTask?.result?.tor_status?.exit_ip }}
                </div>
              </div>
            </q-card>
          </div>
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">CRAWL RESULT</div>
              <div class="column q-gutter-y-xs text-mono">
                <div>
                  <span class="ns-muted">SUCCESS:</span>
                  <q-badge :color="currentTask?.result?.crawl_success ? 'positive' : 'negative'">
                    {{ currentTask?.result?.crawl_success ? 'YES' : 'NO' }}
                  </q-badge>
                </div>
                <div v-if="currentTask?.result?.http_status">
                  <span class="ns-muted">HTTP STATUS:</span> {{ currentTask?.result?.http_status }}
                </div>
                <div v-if="currentTask?.result?.title">
                  <span class="ns-muted">PAGE TITLE:</span> {{ currentTask?.result?.title }}
                </div>
              </div>
            </q-card>
          </div>
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">DISCOVERIES</div>
              <div class="column q-gutter-y-xs text-mono">
                <div>
                  <span class="ns-muted">ONION LINKS:</span>
                  <span class="text-primary">{{ currentTask?.result?.onion_links_count ?? 0 }}</span>
                </div>
                <div>
                  <span class="ns-muted">EMAILS FOUND:</span>
                  <span class="text-warning">{{ currentTask?.result?.emails_found?.length ?? 0 }}</span>
                </div>
              </div>
            </q-card>
          </div>
        </div>

        <!-- Error state -->
        <div v-if="currentTask?.result?.error" class="q-mb-lg">
          <q-banner class="bg-warning text-black rounded-borders">
            <template v-slot:avatar><q-icon name="warning" /></template>
            {{ currentTask?.result?.error }}
          </q-banner>
        </div>

        <!-- Text Excerpt -->
        <div v-if="currentTask?.result?.text_excerpt" class="q-mb-lg">
          <div class="ns-label q-mb-sm">PAGE TEXT EXCERPT</div>
          <q-card flat class="ns-report-block q-pa-md">
            <div class="text-mono text-caption" style="white-space: pre-wrap; color: #94a3b8; max-height: 200px; overflow-y: auto">
              {{ currentTask?.result?.text_excerpt }}
            </div>
          </q-card>
        </div>

        <!-- Discovered .onion Links -->
        <div v-if="currentTask?.result?.onion_links_discovered?.length" class="q-mb-lg">
          <div class="ns-label q-mb-sm">.ONION LINKS DISCOVERED ({{ currentTask?.result?.onion_links_discovered?.length }})</div>
          <q-card flat class="ns-report-block q-pa-md">
            <div class="column q-gutter-y-xs">
              <div
                v-for="link in currentTask?.result?.onion_links_discovered"
                :key="link"
                class="ns-code ns-report-value"
                style="color: #a855f7"
              >
                {{ link }}
              </div>
            </div>
          </q-card>
        </div>

        <!-- Emails Found -->
        <div v-if="currentTask?.result?.emails_found?.length" class="q-mb-lg">
          <div class="ns-label q-mb-sm">EMAIL ADDRESSES FOUND</div>
          <q-card flat class="ns-report-block q-pa-md">
            <div class="row q-gutter-sm">
              <q-chip
                v-for="email in currentTask?.result?.emails_found"
                :key="email"
                color="bg-surface"
                text-color="warning"
                icon="email"
              >{{ email }}</q-chip>
            </div>
          </q-card>
        </div>
      </section>

      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- THEATER 2: PHONE LOOKUP RESULTS                           -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      <section v-if="currentTask?.module === 'phone'" class="ns-report-card q-pa-xl q-mb-xl" style="border-color: rgba(56,189,248,0.4)">
        <div class="row items-center q-gutter-x-sm q-mb-lg">
          <Phone :size="24" style="color:#38bdf8" />
          <div>
            <div class="ns-label" style="color:#38bdf8">THEATER II — PHONE CARRIER INTELLIGENCE</div>
            <h2 class="ns-heading-md text-white q-ma-none">{{ currentTask?.result?.normalized || currentTask?.target }}</h2>
          </div>
        </div>

        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">NUMBER DETAILS</div>
              <div class="column q-gutter-y-xs text-mono">
                <div><span class="ns-muted">INPUT:</span> {{ currentTask?.result?.input }}</div>
                <div><span class="ns-muted">NORMALIZED:</span> {{ currentTask?.result?.normalized }}</div>
                <div>
                  <span class="ns-muted">VALID:</span>
                  <q-badge :color="currentTask?.result?.valid ? 'positive' : 'negative'">
                    {{ currentTask?.result?.valid ? 'YES' : 'NO' }}
                  </q-badge>
                </div>
                <div><span class="ns-muted">IS MOBILE:</span> {{ currentTask?.result?.is_mobile ?? 'UNKNOWN' }}</div>
              </div>
            </q-card>
          </div>
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">CARRIER DATA</div>
              <div class="column q-gutter-y-xs text-mono">
                <div><span class="ns-muted">CARRIER:</span> {{ currentTask?.result?.carrier || 'N/A' }}</div>
                <div><span class="ns-muted">LINE TYPE:</span> {{ currentTask?.result?.line_type || 'N/A' }}</div>
                <div><span class="ns-muted">LOCATION:</span> {{ currentTask?.result?.location || 'N/A' }}</div>
              </div>
            </q-card>
          </div>
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">GEO ORIGIN</div>
              <div class="column q-gutter-y-xs text-mono">
                <div><span class="ns-muted">COUNTRY CODE:</span> {{ currentTask?.result?.country_code || 'N/A' }}</div>
                <div><span class="ns-muted">COUNTRY:</span> {{ currentTask?.result?.country_name || 'N/A' }}</div>
                <div><span class="ns-muted">SOURCE:</span> {{ currentTask?.result?.source || 'N/A' }}</div>
              </div>
            </q-card>
          </div>
        </div>
      </section>

      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- THEATER 3: EMAIL HUNT / CREDENTIAL RESULTS                -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      <section v-if="currentTask?.module === 'email'" class="ns-report-card q-pa-xl q-mb-xl" style="border-color: rgba(249,115,22,0.4)">
        <div class="row items-center q-gutter-x-sm q-mb-lg">
          <Mail :size="24" style="color:#f97316" />
          <div>
            <div class="ns-label" style="color:#f97316">THEATER III — IDENTITY & CREDENTIAL HUNTING</div>
            <h2 class="ns-heading-md text-white q-ma-none">{{ currentTask?.target }}</h2>
          </div>
        </div>

        <!-- Summary row -->
        <div class="row q-col-gutter-md q-mb-lg">
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">EMAIL TARGET</div>
              <div class="column q-gutter-y-xs text-mono">
                <div><span class="ns-muted">EMAIL:</span> {{ currentTask?.result?.email }}</div>
                <div><span class="ns-muted">DOMAIN:</span> {{ currentTask?.result?.domain }}</div>
                <div>
                  <span class="ns-muted">MX RECORDS:</span>
                  <span :class="currentTask?.result?.mx_records?.length ? 'text-positive' : 'text-warning'">
                    {{ currentTask?.result?.mx_records?.length ? currentTask?.result?.mx_records?.length + ' found' : 'NONE' }}
                  </span>
                </div>
              </div>
            </q-card>
          </div>
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">GRAVATAR PROFILE</div>
              <div class="row items-center q-gutter-x-md">
                <q-avatar v-if="currentTask?.result?.gravatar?.found" size="52px">
                  <img :src="currentTask?.result?.gravatar?.avatar_url" />
                </q-avatar>
                <div class="column q-gutter-y-xs text-mono">
                  <div>
                    <q-badge :color="currentTask?.result?.gravatar?.found ? 'positive' : 'grey'">
                      {{ currentTask?.result?.gravatar?.found ? 'PROFILE FOUND' : 'NO PROFILE' }}
                    </q-badge>
                  </div>
                  <div v-if="currentTask?.result?.gravatar?.display_name">
                    <span class="ns-muted">NAME:</span> {{ currentTask?.result?.gravatar?.display_name }}
                  </div>
                  <div v-if="currentTask?.result?.gravatar?.location">
                    <span class="ns-muted">LOCATION:</span> {{ currentTask?.result?.gravatar?.location }}
                  </div>
                </div>
              </div>
            </q-card>
          </div>
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">BREACH STATUS</div>
              <div class="column q-gutter-y-xs text-mono">
                <div v-if="currentTask?.result?.breaches !== null">
                  <span class="ns-muted">BREACHES:</span>
                  <span :class="currentTask?.result?.breach_count > 0 ? 'text-negative' : 'text-positive'" class="text-weight-bold">
                    {{ currentTask?.result?.breach_count ?? 0 }}
                  </span>
                </div>
                <div v-if="currentTask?.result?.paste_count !== undefined">
                  <span class="ns-muted">PASTES:</span>
                  <span :class="currentTask?.result?.paste_count > 0 ? 'text-warning' : 'text-positive'">
                    {{ currentTask?.result?.paste_count }}
                  </span>
                </div>
                <div v-if="currentTask?.result?.hibp_note" class="text-caption ns-muted">
                  {{ currentTask?.result?.hibp_note }}
                </div>
              </div>
            </q-card>
          </div>
        </div>

        <!-- Breach list -->
        <div v-if="currentTask?.result?.breaches?.length" class="q-mb-lg">
          <div class="ns-label q-mb-sm">DATA BREACHES ({{ currentTask?.result?.breach_count }})</div>
          <div class="column q-gutter-y-sm">
            <q-card
              v-for="breach in currentTask?.result?.breaches"
              :key="breach.name"
              flat class="ns-report-block q-pa-md"
              style="border-left: 3px solid #ef4444"
            >
              <div class="row items-start justify-between">
                <div>
                  <div class="text-white text-weight-bold">{{ breach.title || breach.name }}</div>
                  <div class="ns-muted text-caption q-mt-xs">{{ breach.breach_date }} · {{ (breach.pwn_count || 0).toLocaleString() }} accounts compromised</div>
                </div>
                <div class="column items-end q-gutter-y-xs">
                  <q-badge v-if="breach.is_sensitive" color="negative">SENSITIVE</q-badge>
                  <q-badge v-if="!breach.is_verified" color="warning">UNVERIFIED</q-badge>
                </div>
              </div>
              <div v-if="breach.data_classes?.length" class="q-mt-sm row q-gutter-xs">
                <q-chip
                  v-for="cls in breach.data_classes"
                  :key="cls"
                  dense size="sm"
                  color="dark" text-color="red-3"
                >{{ cls }}</q-chip>
              </div>
            </q-card>
          </div>
        </div>

        <!-- Gravatar linked accounts -->
        <div v-if="currentTask?.result?.gravatar?.accounts?.length" class="q-mb-lg">
          <div class="ns-label q-mb-sm">LINKED ACCOUNTS (via Gravatar)</div>
          <div class="row q-gutter-sm">
            <q-chip
              v-for="acc in currentTask?.result?.gravatar?.accounts"
              :key="acc.shortname"
              :href="acc.url"
              target="_blank"
              clickable
              color="bg-surface" text-color="primary"
              icon="link"
            >{{ acc.shortname }}</q-chip>
          </div>
        </div>
      </section>

      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- USERNAME MULTI-PLATFORM RESULTS                           -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      </section>
 
      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- THEATER II: IP INTELLIGENCE RESULTS                       -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      <section v-if="currentTask?.module === 'ip'" class="ns-report-card q-pa-lg q-mb-xl" style="border-color: rgba(56,189,248,0.4)">
        <div class="row items-center q-gutter-x-sm q-mb-lg">
          <MapPin :size="24" style="color:#38bdf8" />
          <div>
            <div class="ns-label" style="color:#38bdf8">THEATER II — IP INTELLIGENCE REPORT</div>
            <h2 class="ns-heading-md text-white q-ma-none">{{ currentTask?.target }}</h2>
          </div>
        </div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">NETWORK INFO</div>
              <div class="column q-gutter-y-xs text-mono">
                <div><span class="ns-muted">HOSTNAME:</span> {{ currentTask?.result?.hostname || 'N/A' }}</div>
                <div><span class="ns-muted">ASN:</span> {{ currentTask?.result?.asn || 'N/A' }}</div>
                <div><span class="ns-muted">ISP:</span> {{ currentTask?.result?.isp || 'N/A' }}</div>
              </div>
            </q-card>
          </div>
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">GEOLOCATION</div>
              <div class="column q-gutter-y-xs text-mono">
                <div><span class="ns-muted">CITY:</span> {{ currentTask?.result?.city || 'N/A' }}</div>
                <div><span class="ns-muted">REGION:</span> {{ currentTask?.result?.region || 'N/A' }}</div>
                <div><span class="ns-muted">COUNTRY:</span> {{ currentTask?.result?.country || 'N/A' }}</div>
              </div>
            </q-card>
          </div>
          <div class="col-12 col-md-4">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">SECURITY SIGNALS</div>
              <div class="column q-gutter-y-xs text-mono">
                <div class="row items-center justify-between">
                  <span class="ns-muted">PROXY/VPN:</span>
                  <q-badge :color="currentTask?.result?.is_proxy ? 'negative' : 'positive'">{{ currentTask?.result?.is_proxy ? 'YES' : 'CLEAN' }}</q-badge>
                </div>
                <div class="row items-center justify-between">
                  <span class="ns-muted">TOR NODE:</span>
                  <q-badge :color="currentTask?.result?.is_tor ? 'negative' : 'positive'">{{ currentTask?.result?.is_tor ? 'YES' : 'CLEAN' }}</q-badge>
                </div>
              </div>
            </q-card>
          </div>
        </div>
      </section>

      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- THEATER II: WEB SCRAPER RESULTS                           -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      <section v-if="currentTask?.module === 'scraper'" class="ns-report-card q-pa-lg q-mb-xl" style="border-color: rgba(56,189,248,0.4)">
        <div class="row items-center q-gutter-x-sm q-mb-lg">
          <Code :size="24" style="color:#7dd3fc" />
          <div>
            <div class="ns-label" style="color:#7dd3fc">THEATER II — WEB ASSET ANALYSIS</div>
            <h2 class="ns-heading-sm text-white q-ma-none ellipsis">{{ currentTask?.target }}</h2>
          </div>
        </div>
        <q-card flat class="ns-report-block q-pa-md q-mb-md">
          <div class="ns-label q-mb-sm">PAGE TITLE & DESCRIPTION</div>
          <div class="text-h6 text-white q-mb-xs">{{ currentTask?.result?.title || 'No Title Found' }}</div>
          <p class="ns-muted q-ma-none text-caption">{{ currentTask?.result?.meta_description || 'No meta description provided.' }}</p>
        </q-card>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-sm-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">H1 HEADERS</div>
              <div v-if="currentTask?.result?.h1?.length" class="column q-gutter-y-xs">
                <div v-for="h in currentTask.result.h1" :key="h" class="text-mono text-caption text-info text-italic"># {{ h }}</div>
              </div>
              <div v-else class="ns-muted italic">No H1 tags detected</div>
            </q-card>
          </div>
          <div class="col-12 col-sm-6">
            <q-card flat class="ns-report-block q-pa-md">
              <div class="ns-label q-mb-sm">OUTBOUND LINKS (SAMPLE)</div>
              <div v-if="currentTask?.result?.links_sample?.length" class="column q-gutter-y-xs">
                <div v-for="link in currentTask.result.links_sample" :key="link" class="text-mono text-caption ellipsis text-blue-3">→ {{ link }}</div>
              </div>
              <div v-else class="ns-muted italic">No links extracted</div>
            </q-card>
          </div>
        </div>
      </section>

      <!-- ═══════════════════════════════════════════════════════════ -->
      <!-- THEATER III: METADATA EXTRACTION RESULTS                  -->
      <!-- ═══════════════════════════════════════════════════════════ -->
      <section v-if="currentTask?.module === 'metadata'" class="ns-report-card q-pa-lg q-mb-xl" style="border-color: rgba(249,115,22,0.4)">
        <div class="row items-center q-gutter-x-sm q-mb-lg">
          <FileSearch :size="24" style="color:#fb923c" />
          <div>
            <div class="ns-label" style="color:#fb923c">THEATER III — FORENSIC METADATA</div>
            <h2 class="ns-heading-md text-white q-ma-none">Image Forensics</h2>
          </div>
        </div>
        <div class="row q-col-gutter-md">
          <div class="col-12 col-md-5">
            <q-img :src="currentTask?.target" class="rounded-borders border-ns" fit="contain" style="max-height: 250px" />
          </div>
          <div class="col-12 col-md-7">
            <q-card flat class="ns-report-block q-pa-md full-height">
              <div class="ns-label q-mb-md">EXIF ATTRIBUTES</div>
              <div class="column q-gutter-y-sm text-mono">
                <div class="row justify-between"><span class="ns-muted">CAMERA:</span> <span>{{ currentTask?.result?.camera_make || 'N/A' }} {{ currentTask?.result?.camera_model }}</span></div>
                <div class="row justify-between"><span class="ns-muted">CAPTURED:</span> <span>{{ currentTask?.result?.datetime_original || 'N/A' }}</span></div>
                <div class="row justify-between"><span class="ns-muted">TAGS FOUND:</span> <span>{{ currentTask?.result?.tag_count || 0 }}</span></div>
                <div class="ns-label q-mt-md" style="font-size: 10px">SOURCE URL</div>
                <div class="text-info ellipsis" style="font-size: 11px">{{ currentTask?.target }}</div>
              </div>
            </q-card>
          </div>
        </div>
      </section>
 
      <section v-if="currentTask?.module === 'username'" class="ns-report-card q-pa-xl q-mb-xl" style="border-color: rgba(20,184,166,0.4)">
        <div class="row items-center q-gutter-x-sm q-mb-lg">
          <User :size="24" style="color:#14b8a6" />
          <div>
            <div class="ns-label" style="color:#14b8a6">THEATER III — USERNAME RECON</div>
            <h2 class="ns-heading-md text-white q-ma-none">{{ currentTask?.target }}</h2>
            <div class="ns-muted text-caption">
              Found on {{ currentTask?.result?.profiles_found }}/{{ currentTask?.result?.platforms_checked }} platforms
            </div>
          </div>
        </div>

        <div class="row q-col-gutter-md">
          <div
            v-for="platform in (currentTask?.result?.platforms || [])"
            :key="platform.platform"
            class="col-12 col-md-6"
          >
            <q-card flat class="ns-report-block q-pa-md" :style="platform.profile_found ? 'border-left: 3px solid #14b8a6' : ''">
              <div class="row items-center justify-between q-mb-sm">
                <div class="text-white text-weight-bold">{{ platform.platform }}</div>
                <q-badge :color="platform.profile_found ? 'positive' : 'grey'">
                  {{ platform.profile_found ? 'FOUND' : 'NOT FOUND' }}
                </q-badge>
              </div>
              <div class="column q-gutter-y-xs text-mono text-caption ns-muted">
                <div v-if="platform.display_name || platform.bio">
                  <div v-if="platform.display_name"><span style="color:#94a3b8">NAME:</span> {{ platform.display_name }}</div>
                  <div v-if="platform.bio"><span style="color:#94a3b8">BIO:</span> {{ platform.bio }}</div>
                </div>
                <div v-if="platform.karma !== undefined"><span style="color:#94a3b8">KARMA:</span> {{ platform.karma?.toLocaleString() }}</div>
                <div v-if="platform.account_age_days !== undefined"><span style="color:#94a3b8">ACCOUNT AGE:</span> {{ platform.account_age_days }} days</div>
                <div v-if="platform.submission_count !== undefined"><span style="color:#94a3b8">SUBMISSIONS:</span> {{ platform.submission_count }}</div>
                <div v-if="platform.profile_found">
                  <a :href="platform.url" target="_blank" class="text-primary" style="font-size: 11px">→ {{ platform.url }}</a>
                </div>
                <div v-if="platform.error" class="text-warning">{{ platform.error }}</div>
              </div>
            </q-card>
          </div>
        </div>
      </section>

      <q-tabs
        v-model="activeTab"
        dense
        class="ns-tabs text-grey"
        active-color="primary"
        indicator-color="primary"
        align="left"
        narrow-indicator
      >
        <q-tab name="summary" label="SUMMARY" class="ns-label" />
        <q-tab name="raw" label="RAW DATA" class="ns-label" />
        <q-tab name="table" label="TABLE VIEW" class="ns-label" />
        <q-tab v-if="hasMapData" name="map" label="GEOSPATIAL" class="ns-label" />
        <q-tab name="related" label="RELATED" class="ns-label" />
      </q-tabs>

      <q-separator dark class="q-mb-lg opacity-1" />

      <q-tab-panels v-model="activeTab" animated background-color="transparent" transition-duration="150" class="bg-transparent">
        <!-- SUMMARY TAB -->
        <q-tab-panel name="summary" class="q-pa-none">
          <div class="row q-col-gutter-lg">
            <div v-for="(val, key) in summaryData" :key="key" class="col-12 col-sm-6 col-md-4">
              <q-card flat class="ns-summary-cell q-pa-md">
                <div class="ns-label text-muted q-mb-xs">{{ formatKey(key) }}</div>
                <div class="text-mono text-weight-bold text-white ellipsis">{{ val }}</div>
              </q-card>
            </div>
          </div>
          
          <div class="q-mt-xl" v-if="currentTask?.result?.risk_score">
            <div class="row items-center justify-between q-mb-sm">
              <span class="ns-label">CONFIDENCE / RISK ASSESSMENT</span>
              <span class="text-mono text-primary">{{ currentTask?.result?.risk_score }}%</span>
            </div>
            <q-linear-progress 
              :value="currentTask?.result?.risk_score / 100" 
              color="primary" 
              size="12px" 
              class="rounded-borders ns-progress-bg"
            />
          </div>
        </q-tab-panel>

        <!-- RAW DATA TAB -->
        <q-tab-panel name="raw" class="q-pa-none">
          <div class="ns-json-header row items-center q-mb-md">
            <q-input 
              v-model="jsonFilter" 
              dense 
              filled 
              placeholder="FILTER NODES..." 
              class="col text-mono" 
              dark
            />
          </div>
          <div class="ns-json-tree bg-surface q-pa-md rounded-borders border-ns">
            <vue-json-pretty
              :data="currentTask?.result"
              :deep="3"
              showLine
              showIcon
              @click="onJsonNodeClick"
              theme="dark"
            />
          </div>
        </q-tab-panel>

        <!-- TABLE VIEW TAB -->
        <q-tab-panel name="table" class="q-pa-none">
          <q-table
            :rows="tableData"
            :columns="tableColumns"
            flat
            dark
            bordered
            class="ns-results-table"
          />
        </q-tab-panel>

        <!-- MAP TAB -->
        <q-tab-panel name="map" class="q-pa-none">
          <div id="result-map" class="ns-map-container rounded-borders border-ns"></div>
        </q-tab-panel>

        <!-- RELATED TAB -->
        <q-tab-panel name="related" class="q-pa-none">
          <div class="ns-label q-mb-md">SUGGESTED FOLLOW-UP QUERIES</div>
          <div class="row q-gutter-sm">
            <q-chip 
              v-for="query in relatedQueries" 
              :key="query" 
              clickable 
              @click="dispatchSearch(query)"
              color="bg-surface"
              text-color="primary"
              class="ns-related-chip"
              icon="radar"
            >
              {{ query }}
            </q-chip>
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </div>

    <!-- FAILED STATE -->
    <div v-if="currentTask?.status === 'failed'" class="column flex-center q-py-xl">
      <q-banner class="bg-negative text-white rounded-borders q-pa-lg">
        <template v-slot:avatar>
          <q-icon name="warning" size="md" />
        </template>
        <div class="text-h6">INVESTIGATION TERMINATED PREMATURELY</div>
        <div class="text-mono q-mt-sm">{{ currentTask?.error || 'ERROR_UNKNOWN_TERMINATION' }}</div>
      </q-banner>
      <div class="row q-gutter-x-md q-mt-xl">
        <q-btn color="white" text-color="black" label="RETRY" @click="startPolling" />
        <q-btn color="primary" label="NEW SEARCH" to="/search" />
      </div>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useResultsStore } from 'src/stores/resultsStore'
import { useQuasar, copyToClipboard, QTableProps } from 'quasar'
import {
  Target, User, Globe, MapPin, FileSearch,
  Navigation, Code, Layers, Search, Eye, Phone, Mail, Shield
} from 'lucide-vue-next'
import VueJsonPretty from 'vue-json-pretty'
import 'vue-json-pretty/lib/styles.css'

const $q = useQuasar()
const route = useRoute()
const router = useRouter()
const resultsStore = useResultsStore()

const taskId = computed(() => route.params.taskId as string)
const activeTab = ref((route.hash.replace('#', '') as string) || 'summary')
const jsonFilter = ref('')
const currentTask = computed(() => resultsStore.taskData)
let pollInterval: any = null

// Tab persistence
watch(activeTab, (val) => {
  window.location.hash = val
  if (val === 'map') initMap()
})

onMounted(() => {
  startPolling()
})

onUnmounted(() => {
  clearInterval(pollInterval)
  resultsStore.reset()
})

const startPolling = () => {
  resultsStore.startPolling(taskId.value)
}

watch(() => currentTask.value?.status, (newStatus) => {
  if (newStatus === 'completed') {
    if (activeTab.value === 'map') nextTick(() => initMap())
  }
})

// Visualization Logic
const summaryData = computed(() => {
  if (!currentTask.value?.result) return {}
  const res = currentTask.value.result
  return {
    'PRIMARY_HOST': res.domain,
    'RESOLVED_IP': res.ip,
    'PRIMARY_MX': res.records?.MX,
    'ASN': 'AS15169',
    'CITY': res.location?.city,
    'COUNTRY': res.location?.country
  }
})

const isDomainTask = computed(() => currentTask.value?.module === 'domain')

const domainResult = computed(() => {
  if (!isDomainTask.value || !currentTask.value?.result) return null
  return currentTask.value.result as Record<string, any>
})

const domainSummaryCards = computed(() => {
  if (!domainResult.value) return []
  const records = domainResult.value.records || {}
  return [
    { label: 'DOMAIN', value: domainResult.value.domain || currentTask.value?.target || 'UNKNOWN' },
    { label: 'SOURCE', value: domainResult.value.source || 'dns_asyncresolver' },
    { label: 'RECORD TYPES', value: Object.keys(records).length || 0 },
  ]
})

const dnsParameterEntries = computed(() => {
  const records = domainResult.value?.records || {}
  return Object.entries(records).map(([type, values]) => ({
    type,
    values: Array.isArray(values) ? values : [String(values)],
    count: Array.isArray(values) ? values.length : 1,
  }))
})

const hasMapData = computed(() => !!currentTask.value?.result?.location)

const tableData = computed(() => [currentTask.value?.result])
const tableColumns: QTableProps['columns'] = [
  { name: 'field', label: 'FIELD', field: (row: any) => Object.keys(row)[0], align: 'left', classes: 'ns-label' },
  { name: 'value', label: 'VALUE', field: (row: any) => Object.values(row)[0], align: 'left' }
]

// Map Initialization
let map: any = null
const initMap = async () => {
  if (!hasMapData.value) return
  
  // Dynamic Leaflet Import
  const L = (await import('leaflet')).default
  import ('leaflet/dist/leaflet.css')

  nextTick(() => {
    const loc = currentTask.value?.result?.location
    if (!loc) return
    if (map) return
    
    map = L.map('result-map').setView([loc.lat, loc.lng], 12)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '&copy; CartoDB'
    }).addTo(map)
    
    L.marker([loc.lat, loc.lng]).addTo(map)
      .bindPopup(`<b>${loc.city}, ${loc.country}</b><br>${currentTask.value?.target}`)
      .openPopup()
  })
}

// Helpers
const getStatusColor = computed(() => {
  const s = currentTask.value?.status
  if (s === 'completed') return 'positive'
  if (s === 'processing') return 'blue'
  if (s === 'failed') return 'negative'
  return 'grey'
})

const getModuleColor = computed(() => {
  const t = currentTask.value?.module
  if (t === 'domain')  return 'indigo-7'
  if (t === 'darkweb') return 'purple-7'
  if (t === 'phone')   return 'blue-7'
  if (t === 'email')   return 'orange-7'
  if (t === 'username') return 'teal-7'
  return 'primary'
})

const getActiveModuleIcon = computed(() => {
  const t = currentTask.value?.module
  if (t === 'domain')   return Globe
  if (t === 'username') return User
  if (t === 'darkweb')  return Eye
  if (t === 'phone')    return Phone
  if (t === 'email')    return Mail
  if (t === 'ip')       return MapPin
  return Layers
})

const formatKey = (key: string) => key.replace(/_/g, ' ')

const formatDomainDate = (value?: string | null) => {
  if (!value) return 'N/A'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString()
}

const copyTaskId = () => {
  copyToClipboard(taskId.value).then(() => {
    $q.notify({ message: 'Task ID copied to clipboard', color: 'positive', position: 'bottom' })
  })
}

const exportJson = () => {
  const data = JSON.stringify(currentTask.value, null, 2)
  const blob = new Blob([data], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `nexus_task_${taskId.value}.json`
  a.click()
}

const copyRaw = () => {
  copyToClipboard(JSON.stringify(currentTask.value, null, 2)).then(() => {
    $q.notify({ message: 'Raw data copied', color: 'primary' })
  })
}

const printReport = () => {
  window.print()
}

const relatedQueries = ['Scan Subdomains', 'Reverse IP Lookup', 'Analyze ASN AS15169']
const dispatchSearch = (query: string) => {
  router.push(`/search?target=${query}`)
}

const onJsonNodeClick = (path: string) => {
  console.log('JSON Path selected:', path)
}
</script>

<style scoped>
.ns-report-card {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  border-radius: var(--ns-radius-lg);
}

.ns-report-block {
  background: var(--ns-bg-elevated);
  border: 1px solid var(--ns-border);
  border-radius: var(--ns-radius-md);
}

.ns-report-value {
  word-break: break-word;
  white-space: pre-wrap;
}

.ns-polling-card {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  width: 100%;
  max-width: 600px;
}

.ns-terminal-output {
  height: 200px;
  overflow-y: auto;
  border: 1px solid var(--ns-border);
}

.ns-summary-cell {
  background: var(--ns-bg-surface);
  border: 1px solid var(--ns-border);
  transition: var(--ns-transition);
}

.ns-summary-cell:hover {
  background: var(--ns-bg-elevated);
  border-color: var(--ns-accent);
}

.ns-map-container {
  height: 400px;
  background: var(--ns-bg-surface);
}

.ns-json-tree {
  max-height: 600px;
  overflow: auto;
}

.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

.animate-bounce {
  animation: bounce 1s infinite;
}

@keyframes bounce {
  0%, 100% { transform: translateY(-10%); animation-timing-function: cubic-bezier(0.8, 1, 1); }
  50% { transform: translateY(0); animation-timing-function: cubic-bezier(0, 0, 0.2, 1); }
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.ns-accent-text { color: var(--ns-accent); }
.border-ns { border: 1px solid var(--ns-border); }
.ns-progress-bg { background-color: var(--ns-bg-surface); }
.hover-accent:hover { color: var(--ns-accent); transition: color 0.2s; }

/* JSON Tree Styles Override */
:deep(.vjs-tree) { border: none !important; }
:deep(.vjs-value__string) { color: var(--ns-accent); }
:deep(.vjs-key) { color: #fff; }
</style>
