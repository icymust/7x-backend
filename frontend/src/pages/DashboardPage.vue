<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import Chart from 'primevue/chart'
import DashboardMiniMap from '../components/DashboardMiniMap.vue'
import { useTheme } from '../composables/useTheme'
import { hiringStats, hiringPipeline } from '../data/hiringData'
import { warehouses, demandHistoryByWarehouse } from '../data/warehouseData'
import { notifications, NOTIFICATION_STATUS_COLOR } from '../data/notificationsData'

const router = useRouter()
const { isDark } = useTheme()

function goToMap() {
  router.push('/map')
}

function goToNotifications() {
  router.push('/notifications')
}

const recentNotifications = notifications.slice(0, 4)
const unreadNotifications = notifications.filter((n) => !n.read).length

const maxPipelineCount = hiringPipeline[0].count

function pipelineWidth(count: number) {
  return `${Math.round((count / maxPipelineCount) * 100)}%`
}

const totalWarehouses = warehouses.features.length
const totalActiveShipments = warehouses.features.reduce((sum, f) => sum + f.properties.activeShipments, 0)
const shortageCount = warehouses.features.filter((f) => f.properties.driverStatus === 'shortage').length

const aggregateHistory = computed(() => {
  const histories = Object.values(demandHistoryByWarehouse)
  const labels = histories[0].map((point) => point.month)
  return labels.map((month, i) => ({
    month,
    demand: histories.reduce((sum, history) => sum + history[i].demand, 0),
    projected: histories[0][i].projected,
  }))
})

// Mock utilized capacity - tracks the shape of the demand curve a step
// behind it, so the line rises alongside demand but always stays under it.
const capacityData = computed(() => aggregateHistory.value.map((d) => Math.round((d.demand * 0.82) / 10) * 10))

const chartData = computed(() => {
  const history = aggregateHistory.value
  const lastActualIndex = history.findIndex((d) => d.projected) - 1
  const lineColor = isDark.value ? '#4A7DFF' : '#0020F5'
  const capacityColor = isDark.value ? 'rgba(255,255,255,0.35)' : 'rgba(15,21,32,0.35)'

  return {
    labels: history.map((d) => d.month),
    datasets: [
      {
        label: 'Network Demand',
        data: history.map((d) => (d.projected ? null : d.demand)),
        borderColor: lineColor,
        backgroundColor: isDark.value ? 'rgba(74, 125, 255, 0.18)' : 'rgba(0, 32, 245, 0.1)',
        tension: 0.35,
        fill: true,
        pointRadius: 3,
        borderWidth: 2.5,
      },
      {
        label: 'Forecast',
        data: history.map((d, i) => (i >= lastActualIndex ? d.demand : null)),
        borderColor: lineColor,
        borderDash: [6, 4],
        backgroundColor: 'transparent',
        tension: 0.35,
        fill: false,
        pointRadius: 3,
        borderWidth: 2.5,
      },
      {
        label: 'Capacity',
        data: capacityData.value,
        borderColor: capacityColor,
        borderDash: [2, 3],
        backgroundColor: 'transparent',
        tension: 0.35,
        fill: false,
        pointRadius: 0,
        borderWidth: 1.5,
      },
    ],
  }
})

const chartOptions = computed(() => {
  const gridColor = isDark.value ? 'rgba(255,255,255,0.08)' : 'rgba(15,21,32,0.06)'
  const textColor = isDark.value ? 'rgba(255,255,255,0.65)' : 'rgba(15,21,32,0.55)'
  return {
    maintainAspectRatio: false,
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        align: 'end',
        labels: { color: textColor, boxWidth: 8, usePointStyle: true, pointStyle: 'circle' },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: textColor } },
      y: { grid: { color: gridColor }, ticks: { color: textColor } },
    },
  }
})

</script>

<template>
  <div class="dashboard">
    <div class="dashboard__inner">
      <header class="dashboard__header">
        <span class="dashboard__eyebrow">Overview</span>
        <h1 class="dashboard__title">Workforce &amp; Hiring Dashboard</h1>
        <p class="dashboard__subtitle">Headcount, pipeline health, and network demand across all branches</p>
      </header>

      <div class="dashboard__grid">
        <div class="dashboard__side-stack">
          <div
            class="dashboard__card dashboard__map-card"
            role="button"
            tabindex="0"
            @click="goToMap"
            @keydown.enter="goToMap"
          >
            <DashboardMiniMap />

            <div class="dashboard__map-header-overlay">
              <h3 class="dashboard__card-title dashboard__card-title--flush">Warehouse Map</h3>
              <i class="pi pi-arrow-up-right dashboard__map-icon" />
            </div>

            <div class="dashboard__map-stats dashboard__map-stats-overlay">
              <div class="dashboard__map-stat">
                <span class="dashboard__map-stat-value">{{ totalWarehouses }}</span>
                <span class="dashboard__map-stat-label">Warehouses</span>
              </div>
              <div class="dashboard__map-stat">
                <span class="dashboard__map-stat-value">{{ totalActiveShipments }}</span>
                <span class="dashboard__map-stat-label">Active Shipments</span>
              </div>
              <div class="dashboard__map-stat">
                <span class="dashboard__map-stat-value">{{ shortageCount }}</span>
                <span class="dashboard__map-stat-label">Driver Shortages</span>
              </div>
            </div>
          </div>

          <div class="dashboard__stats-panel">
            <div v-for="stat in hiringStats" :key="stat.label" class="dashboard__card dashboard__stat">
              <span class="dashboard__stat-icon"><i :class="stat.icon" /></span>
              <div class="dashboard__stat-body">
                <span class="dashboard__stat-value">{{ stat.value }}</span>
                <span class="dashboard__stat-label">{{ stat.label }}</span>
                <span class="dashboard__stat-trend" :class="{ 'dashboard__stat-trend--up': stat.trendUp }">
                  <i class="pi pi-arrow-up-right" />{{ stat.trend }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="dashboard__card dashboard__pipeline">
          <h3 class="dashboard__card-title">Hiring Pipeline</h3>
          <div class="pipeline">
            <div v-for="stage in hiringPipeline" :key="stage.label" class="pipeline__row">
              <div class="pipeline__row-header">
                <span class="pipeline__label">{{ stage.label }}</span>
                <span class="pipeline__count">{{ stage.count }}</span>
              </div>
              <div class="pipeline__track">
                <div class="pipeline__fill" :style="{ width: pipelineWidth(stage.count) }" />
              </div>
            </div>
          </div>
        </div>

        <div class="dashboard__card dashboard__chart">
          <h3 class="dashboard__card-title">Network Demand Trend</h3>
          <div class="dashboard__chart-canvas">
            <Chart type="line" :data="chartData" :options="chartOptions" />
          </div>
        </div>

        <div class="dashboard__card dashboard__notifications">
          <div class="dashboard__card-header">
            <h3 class="dashboard__card-title dashboard__card-title--flush">Notifications</h3>
            <span v-if="unreadNotifications" class="dashboard__notifications-badge">{{ unreadNotifications }} unread</span>
          </div>
          <div class="notifications-preview">
            <div
              v-for="n in recentNotifications"
              :key="n.id"
              class="notifications-preview__row"
              :class="{ 'notifications-preview__row--unread': !n.read }"
            >
              <span
                class="notifications-preview__dot"
                :style="{ '--status-color': NOTIFICATION_STATUS_COLOR[n.status] }"
              />
              <div class="notifications-preview__info">
                <span class="notifications-preview__title">{{ n.title }}</span>
                <span class="notifications-preview__time">{{ n.timestamp }}</span>
              </div>
            </div>
          </div>
          <Button
            label="View All Notifications"
            text
            size="small"
            icon="pi pi-arrow-right"
            icon-pos="right"
            class="dashboard__notifications-cta"
            @click="goToNotifications"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow-y: auto;
}

.dashboard__inner {
  max-width: 78rem;
  margin: 0 auto;
  padding: 1.5rem 2.25rem;
  box-sizing: border-box;
}

.dashboard__header {
  margin-bottom: 1.1rem;
}

.dashboard__eyebrow {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--brand-blue);
}

.dashboard__title {
  margin: 0.15rem 0 0.25rem;
  font-size: 1.35rem;
  font-weight: 700;
  color: var(--p-text-color);
  letter-spacing: -0.01em;
}

.dashboard__subtitle {
  margin: 0;
  font-size: 0.85rem;
  color: var(--p-text-muted-color);
}

.dashboard__grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  grid-template-rows: auto auto;
  grid-template-areas:
    'chart chart side side'
    'notifications notifications pipeline pipeline';
  gap: 0.75rem;
}

.dashboard__side-stack {
  grid-area: side;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dashboard__stats-panel {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-template-rows: repeat(2, 1fr);
  gap: 0.75rem;
}

.dashboard__card {
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.9rem;
  padding: 0.9rem 1.1rem;
  overflow: hidden;
}

.dashboard__card-title {
  flex-shrink: 0;
  margin: 0 0 0.5rem;
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.dashboard__card-title--flush {
  margin: 0;
}

.dashboard__card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.6rem;
}

.dashboard__notifications-badge {
  flex-shrink: 0;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--brand-blue);
  background: rgba(74, 125, 255, 0.12);
}

.dashboard__stat {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 0.35rem;
}

.dashboard__stat-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 0.6rem;
  background: rgba(74, 125, 255, 0.12);
  color: var(--brand-blue);
  font-size: 0.95rem;
  flex-shrink: 0;
}

.dashboard__stat-body {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.dashboard__stat-value {
  font-size: 1.2rem;
  font-weight: 700;
  color: var(--p-text-color);
  letter-spacing: -0.02em;
}

.dashboard__stat-label {
  font-size: 0.72rem;
  color: var(--p-text-muted-color);
}

.dashboard__stat-trend {
  margin-top: 0.15rem;
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.68rem;
  color: var(--p-text-muted-color);
}

.dashboard__stat-trend--up {
  color: #16a34a;
}

.dashboard__pipeline {
  grid-area: pipeline;
}

.pipeline {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.pipeline__row {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.pipeline__row-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.pipeline__label {
  font-size: 0.78rem;
  color: var(--p-text-muted-color);
}

.pipeline__track {
  height: 0.45rem;
  border-radius: 999px;
  background: var(--p-surface-200);
  overflow: hidden;
}

.pipeline__fill {
  height: 100%;
  border-radius: 999px;
  background: var(--brand-blue);
}

.pipeline__count {
  flex-shrink: 0;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.dashboard__chart {
  grid-area: chart;
}

.dashboard__chart-canvas {
  aspect-ratio: 4 / 3;
  width: 100%;
  position: relative;
}

.dashboard__chart-canvas :deep(.p-chart) {
  height: 100%;
  width: 100%;
}

.dashboard__notifications {
  grid-area: notifications;
  display: flex;
  flex-direction: column;
}

.notifications-preview {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  flex: 1;
}

.notifications-preview__row {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  padding-bottom: 0.55rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.notifications-preview__row:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.notifications-preview__dot {
  flex-shrink: 0;
  margin-top: 0.3rem;
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 50%;
  border: 1.5px solid var(--status-color);
  background: transparent;
}

.notifications-preview__row--unread .notifications-preview__dot {
  background: var(--status-color);
}

.notifications-preview__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.notifications-preview__title {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--p-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notifications-preview__row--unread .notifications-preview__title {
  font-weight: 700;
}

.notifications-preview__time {
  font-size: 0.7rem;
  color: var(--p-text-muted-color);
}

.dashboard__notifications-cta.p-button {
  align-self: flex-start;
  margin-top: 0.6rem;
  padding: 0;
  font-size: 0.78rem;
}

.dashboard__map-card {
  position: relative;
  min-height: 17rem;
  padding: 0;
  cursor: pointer;
  text-align: left;
  font-family: var(--font-sans);
  transition: border-color 0.15s ease;
}

.dashboard__map-card:hover {
  border-color: var(--brand-blue);
}

.dashboard__map-header-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding: 0.85rem 1rem;
  background: linear-gradient(
    to bottom,
    color-mix(in srgb, var(--p-content-background) 90%, transparent) 0%,
    transparent 100%
  );
}

.dashboard__map-icon {
  flex-shrink: 0;
  font-size: 0.78rem;
  color: var(--p-text-muted-color);
}

.dashboard__map-stats-overlay {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 1;
  padding: 1.5rem 1rem 0.9rem;
  background: linear-gradient(
    to top,
    color-mix(in srgb, var(--p-content-background) 94%, transparent) 45%,
    transparent 100%
  );
}

.dashboard__map-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.25rem;
}

.dashboard__map-stat {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.dashboard__map-stat-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--p-text-color);
  letter-spacing: -0.01em;
}

.dashboard__map-stat-label {
  font-size: 0.7rem;
  color: var(--p-text-muted-color);
}

</style>
