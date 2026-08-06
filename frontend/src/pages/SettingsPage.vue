<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Button from 'primevue/button'
import {
  fetchServiceHealth,
  type ServiceHealth,
} from '../services/healthApi'

const services = ref<ServiceHealth[]>([])
const loading = ref(false)
const checkedAt = ref<Date | null>(null)

const availableCount = computed(
  () => services.value.filter((service) => service.available).length,
)

const checkedAtLabel = computed(() => {
  if (!checkedAt.value) return 'Not checked yet'

  return `Last checked at ${checkedAt.value.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })}`
})

async function refreshHealth() {
  loading.value = true

  try {
    services.value = await fetchServiceHealth()
    checkedAt.value = new Date()
  } finally {
    loading.value = false
  }
}

onMounted(refreshHealth)
</script>

<template>
  <div class="settings">
    <div class="settings__inner">
      <header class="settings__header">
        <div>
          <span class="settings__eyebrow">System</span>
          <h1 class="settings__title">Settings</h1>
          <p class="settings__subtitle">Service connections used by the workforce platform.</p>
        </div>

        <Button
          label="Refresh"
          icon="pi pi-refresh"
          outlined
          size="small"
          :loading="loading"
          @click="refreshHealth"
        />
      </header>

      <section class="settings__card">
        <div class="settings__card-header">
          <div>
            <h2>Service health</h2>
            <p>{{ checkedAtLabel }}</p>
          </div>
          <span v-if="services.length" class="settings__summary">
            {{ availableCount }} / {{ services.length }} connected
          </span>
        </div>

        <div v-if="loading && !services.length" class="settings__loading">
          <i class="pi pi-spin pi-spinner" /> Checking connections...
        </div>

        <div v-else class="settings__services">
          <article
            v-for="service in services"
            :key="service.id"
            class="settings__service"
          >
            <span
              class="settings__status-dot"
              :class="service.available
                ? 'settings__status-dot--online'
                : 'settings__status-dot--offline'"
              :aria-label="service.available ? 'Connected' : 'Unavailable'"
            />

            <div class="settings__service-info">
              <div class="settings__service-heading">
                <strong>{{ service.name }}</strong>
                <span
                  class="settings__status-label"
                  :class="service.available
                    ? 'settings__status-label--online'
                    : 'settings__status-label--offline'"
                >
                  {{ service.available ? 'Connected' : 'Unavailable' }}
                </span>
              </div>
              <span class="settings__service-description">{{ service.description }}</span>
              <small>{{ service.details }}</small>
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.settings {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow-y: auto;
}

.settings__inner {
  max-width: 52rem;
  margin: 0 auto;
  padding: 1.5rem 2.25rem 3rem;
  box-sizing: border-box;
}

.settings__header,
.settings__card-header,
.settings__service-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}

.settings__header {
  margin-bottom: 1.5rem;
}

.settings__eyebrow {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--brand-blue);
}

.settings__title {
  margin: 0.15rem 0 0.25rem;
  font-size: 1.35rem;
  color: var(--p-text-color);
}

.settings__subtitle,
.settings__card-header p {
  margin: 0;
  font-size: 0.82rem;
  color: var(--p-text-muted-color);
}

.settings__card {
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.9rem;
  background: var(--p-content-background);
  overflow: hidden;
}

.settings__card-header {
  padding: 1rem 1.15rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.settings__card-header h2 {
  margin: 0 0 0.2rem;
  font-size: 0.95rem;
  color: var(--p-text-color);
}

.settings__summary {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--p-text-muted-color);
}

.settings__loading {
  padding: 2rem;
  text-align: center;
  color: var(--p-text-muted-color);
  font-size: 0.82rem;
}

.settings__services {
  display: flex;
  flex-direction: column;
}

.settings__service {
  display: flex;
  align-items: flex-start;
  gap: 0.85rem;
  padding: 1.05rem 1.15rem;
}

.settings__service + .settings__service {
  border-top: 1px solid var(--p-content-border-color);
}

.settings__status-dot {
  flex: 0 0 auto;
  width: 0.7rem;
  height: 0.7rem;
  margin-top: 0.28rem;
  border-radius: 50%;
  box-shadow: 0 0 0 0.22rem color-mix(in srgb, currentColor 13%, transparent);
}

.settings__status-dot--online {
  color: #16a34a;
  background: #16a34a;
}

.settings__status-dot--offline {
  color: #dc2626;
  background: #dc2626;
}

.settings__service-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.settings__service-heading strong {
  font-size: 0.88rem;
  color: var(--p-text-color);
}

.settings__status-label {
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
}

.settings__status-label--online {
  color: #16a34a;
}

.settings__status-label--offline {
  color: #dc2626;
}

.settings__service-description,
.settings__service-info small {
  color: var(--p-text-muted-color);
  font-size: 0.76rem;
}

.settings__service-info small {
  font-size: 0.7rem;
}

@media (max-width: 700px) {
  .settings__inner {
    padding: 1.25rem;
  }
}
</style>
