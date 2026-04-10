<template>
  <div class="fullscreen ns-not-found flex flex-center">
    <!-- SCAN LINE EFFECT -->
    <div class="scanline"></div>
    
    <div class="text-center q-pa-md relative-position">
      <div class="err-code text-mono">404</div>
      
      <h1 class="ns-heading-lg text-white q-mt-md q-mb-sm">PAGE NOT FOUND</h1>
      
      <p class="ns-muted text-mono q-mb-xl">
        The intelligence you are looking for does not exist.
        <br>
        <span class="text-primary">[ ACCESS_DENIED : TARGET_NULL ]</span>
      </p>

      <q-btn
        color="primary"
        class="ns-btn-tactical q-px-xl q-py-md"
        to="/"
        label="RETURN TO DASHBOARD"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
// Minimal setup for 404 page
</script>

<style scoped>
.ns-not-found {
  background-color: var(--ns-bg-base);
  color: var(--ns-text-primary);
  overflow: hidden;
}

.err-code {
  font-size: 25vh;
  line-height: 1;
  font-weight: 700;
  color: var(--ns-accent);
  opacity: 0.15;
  letter-spacing: -0.05em;
  user-select: none;
}

.ns-btn-tactical {
  font-family: var(--ns-font-mono);
  letter-spacing: 0.1em;
  font-weight: 600;
}

/* SCANLINE ANIMATION */
.scanline {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 2px;
  background: rgba(0, 212, 170, 0.1);
  box-shadow: 0 0 10px rgba(0, 212, 170, 0.2);
  z-index: 100;
  pointer-events: none;
  animation: scan 4s linear infinite;
}

@keyframes scan {
  0% { top: -10%; }
  100% { top: 110%; }
}

@media (max-width: 600px) {
  .err-code {
    font-size: 15vh;
  }
}
</style>
