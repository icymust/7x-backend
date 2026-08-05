<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import { notifications, totalNotificationCount, NOTIFICATION_STATUS_COLOR } from '../data/notificationsData'

const router = useRouter()

const unreadCount = computed(() => notifications.filter((n) => !n.read).length)

// Every notification starts collapsed to just its header; toggling one
// doesn't affect the others.
const expanded = reactive<Record<string, boolean>>({})

function toggle(id: string) {
  expanded[id] = !expanded[id]
}

function goToWarehouse(warehouseName: string) {
  router.push({ path: '/map', query: { warehouse: warehouseName } })
}
</script>

<template>
  <div class="notifications">
    <div class="notifications__inner">
      <header class="notifications__header">
        <span class="notifications__eyebrow">Overview</span>
        <h1 class="notifications__title">Notifications</h1>
        <p class="notifications__subtitle">
          {{ unreadCount }} unread &middot; showing {{ notifications.length }} of {{ totalNotificationCount }}
        </p>
      </header>

      <div class="notifications__list">
        <div
          v-for="n in notifications"
          :key="n.id"
          class="notifications__item"
          :class="{ 'notifications__item--unread': !n.read }"
        >
          <button type="button" class="notifications__item-header" @click="toggle(n.id)">
            <span
              class="notifications__status-dot"
              :class="{ 'notifications__status-dot--filled': !n.read }"
              :style="{ '--status-color': NOTIFICATION_STATUS_COLOR[n.status] }"
            />
            <div class="notifications__item-heading">
              <span class="notifications__item-title">{{ n.title }}</span>
              <span class="notifications__item-time">{{ n.timestamp }}</span>
            </div>
            <i class="pi notifications__item-chevron" :class="expanded[n.id] ? 'pi-chevron-up' : 'pi-chevron-down'" />
          </button>

          <div v-if="expanded[n.id]" class="notifications__item-details">
            <p class="notifications__item-text">{{ n.text }}</p>
            <Button
              v-if="n.warehouseName"
              label="View Warehouse"
              text
              size="small"
              icon="pi pi-arrow-right"
              icon-pos="right"
              class="notifications__item-cta"
              @click="goToWarehouse(n.warehouseName)"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.notifications {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow-y: auto;
}

.notifications__inner {
  max-width: 52rem;
  margin: 0 auto;
  padding: 1.5rem 2.25rem 3rem;
  box-sizing: border-box;
}

.notifications__header {
  margin-bottom: 1.5rem;
}

.notifications__eyebrow {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--brand-blue);
}

.notifications__title {
  margin: 0.15rem 0 0.25rem;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--p-text-color);
  letter-spacing: -0.01em;
}

.notifications__subtitle {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}

.notifications__list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.notifications__item {
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.9rem;
  background: var(--p-content-background);
  overflow: hidden;
}

.notifications__item-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  width: 100%;
  padding: 1rem 1.1rem;
  border: none;
  background: transparent;
  font-family: var(--font-sans);
  text-align: left;
  cursor: pointer;
}

.notifications__status-dot {
  flex-shrink: 0;
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  border: 1.5px solid var(--status-color);
  background: transparent;
}

.notifications__status-dot--filled {
  background: var(--status-color);
}

.notifications__item-heading {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  text-align: left;
}

.notifications__item-title {
  font-size: 0.88rem;
  font-weight: 500;
  color: var(--p-text-color);
}

.notifications__item--unread .notifications__item-title {
  font-weight: 700;
}

.notifications__item-time {
  font-size: 0.72rem;
  color: var(--p-text-muted-color);
}

.notifications__item-chevron {
  flex-shrink: 0;
  font-size: 0.8rem;
  color: var(--p-text-muted-color);
}

.notifications__item-details {
  padding: 0 1.1rem 1.1rem 2.55rem;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
}

.notifications__item-text {
  margin: 0;
  font-size: 0.82rem;
  line-height: 1.45;
  color: var(--p-text-muted-color);
}

.notifications__item-cta.p-button {
  padding: 0;
  font-size: 0.78rem;
}
</style>
