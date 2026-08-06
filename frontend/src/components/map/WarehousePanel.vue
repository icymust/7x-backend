<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { Feature, Point } from 'geojson'
import Button from 'primevue/button'
import IconField from 'primevue/iconfield'
import InputIcon from 'primevue/inputicon'
import InputText from 'primevue/inputtext'
import Chart from 'primevue/chart'
import ProgressBar from 'primevue/progressbar'
import Accordion from 'primevue/accordion'
import AccordionPanel from 'primevue/accordionpanel'
import AccordionHeader from 'primevue/accordionheader'
import AccordionContent from 'primevue/accordioncontent'
import Tabs from 'primevue/tabs'
import TabList from 'primevue/tablist'
import Tab from 'primevue/tab'
import TabPanels from 'primevue/tabpanels'
import TabPanel from 'primevue/tabpanel'
import type { WarehouseProperties } from '../../data/warehouseData'
import {
  DRIVER_STATUS_COLOR,
  DRIVER_STATUS_LABEL,
  demandHistoryByWarehouse,
  mainBranchWarehouse,
  warehouses,
} from '../../data/warehouseData'
import { useTheme } from '../../composables/useTheme'
import { useWarehouseSelection } from '../../composables/useWarehouseSelection'
import DemandCalendar from './DemandCalendar.vue'
import DemandHourlyChart from './DemandHourlyChart.vue'
import WarehouseAiSuggestions from './WarehouseAiSuggestions.vue'
import WarehouseManageActions from './WarehouseManageActions.vue'

const { isDark } = useTheme()
const { selectedWarehouse, showList, selectWarehouse, showWarehouseList } = useWarehouseSelection()
const route = useRoute()

const searchQuery = ref('')

// Tracked (rather than left as the Accordion's uncontrolled default) so
// WarehouseAiSuggestions can tell when its own panel becomes the open one
// and lazy-load its data on that transition instead of on mount.
const accordionValue = ref('metrics')

// Drives which way the list/detail swap slides: forward (right-to-left)
// when drilling into a warehouse, backward (left-to-right) when returning
// to the list - regardless of whether the trigger was a list click, a map
// marker click, or the Back button.
const slideDirection = ref<'forward' | 'backward'>('forward')
watch(showList, (isList) => {
  slideDirection.value = isList ? 'backward' : 'forward'
})

// Opening the warehouses page always starts on the list, even if a
// warehouse was left selected from a previous visit - unless we arrived
// via a deep link (e.g. a notification's "View Warehouse" button), in
// which case that warehouse's detail view opens directly.
onMounted(() => {
  searchQuery.value = ''

  const deepLinkName = route.query.warehouse
  const feature =
    typeof deepLinkName === 'string' ? warehouses.features.find((f) => f.properties.name === deepLinkName) : undefined

  if (feature) {
    selectWarehouse(feature.properties, feature.geometry.coordinates as [number, number])
  } else {
    showList.value = true
  }
})

const filteredWarehouses = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return warehouses.features
  return warehouses.features.filter(
    (f) => f.properties.name.toLowerCase().includes(q) || f.properties.zone.toLowerCase().includes(q),
  )
})

function selectFromList(feature: Feature<Point, WarehouseProperties>) {
  selectWarehouse(feature.properties, feature.geometry.coordinates as [number, number])
}

const active = computed(() => selectedWarehouse.value ?? mainBranchWarehouse)
const isMainBranch = computed(() => active.value.name === mainBranchWarehouse.name)
const healthColor = computed(() => DRIVER_STATUS_COLOR[active.value.driverStatus])

const chartData = computed(() => {
  const history = demandHistoryByWarehouse[active.value.name] ?? []
  const lastActualIndex = history.findIndex((d) => d.projected) - 1
  const lineColor = isDark.value ? '#4A7DFF' : '#0020F5'

  return {
    labels: history.map((d) => d.month),
    datasets: [
      {
        label: 'Demand',
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
  <aside class="warehouse-panel">
    <Transition :name="slideDirection === 'forward' ? 'slide-fwd' : 'slide-back'">
      <div v-if="showList" key="list" class="warehouse-panel__pane">
        <div class="warehouse-panel__header">
          <span class="warehouse-panel__eyebrow">Network</span>
          <h2 class="warehouse-panel__title">Warehouses</h2>
          <span class="warehouse-panel__zone">{{ warehouses.features.length }} locations across Abu Dhabi</span>
        </div>

        <IconField class="warehouse-list__search">
          <InputIcon class="pi pi-search" />
          <InputText v-model="searchQuery" placeholder="Search by name or zone" fluid />
        </IconField>

        <div v-if="filteredWarehouses.length" class="warehouse-list">
          <button
            v-for="f in filteredWarehouses"
            :key="f.properties.name"
            type="button"
            class="warehouse-list__item"
            @click="selectFromList(f)"
          >
            <span class="warehouse-list__item-name">{{ f.properties.name }}</span>
            <span class="warehouse-list__item-zone">{{ f.properties.zone }}</span>
            <div class="warehouse-list__item-meta">
              <span class="warehouse-list__item-metric">
                <i class="pi pi-box" /> {{ f.properties.activeShipments }} shipments
              </span>
              <span
                class="warehouse-list__item-metric"
                :style="{ color: DRIVER_STATUS_COLOR[f.properties.driverStatus] }"
              >
                <i class="pi pi-circle-fill" /> {{ f.properties.courierLoadPercent }}% load
              </span>
            </div>
          </button>
        </div>
        <p v-else class="warehouse-list__empty">No warehouses match "{{ searchQuery }}".</p>
      </div>

      <div v-else key="detail" class="warehouse-panel__pane">
        <div class="warehouse-panel__header">
          <span class="warehouse-panel__eyebrow">{{ isMainBranch ? 'Main Branch' : 'Warehouse' }}</span>
          <div class="warehouse-panel__title-row">
            <Button
              text
              size="small"
              icon="pi pi-arrow-left"
              class="warehouse-panel__reset"
              aria-label="Back to warehouse list"
              @click="showWarehouseList"
            />
            <h2 class="warehouse-panel__title">{{ active.name }}</h2>
          </div>
          <span class="warehouse-panel__zone">{{ active.zone }}</span>
        </div>

        <div class="warehouse-panel__health" :style="{ '--health-color': healthColor }">
          <div class="warehouse-panel__health-header">
            <span class="warehouse-panel__health-label">Warehouse Health</span>
            <span class="warehouse-panel__health-value">{{ active.courierLoadPercent }}%</span>
          </div>
          <ProgressBar
            :value="active.courierLoadPercent"
            :show-value="false"
            class="warehouse-panel__health-bar"
          />
          <span class="warehouse-panel__health-caption">
            {{ DRIVER_STATUS_LABEL[active.driverStatus] }} &middot; based on average courier load
          </span>
        </div>

        <Accordion class="warehouse-panel__accordion" v-model:value="accordionValue">
          <AccordionPanel value="metrics">
            <AccordionHeader>Metrics</AccordionHeader>
            <AccordionContent>
              <div class="warehouse-panel__stats">
                <div class="warehouse-panel__stat">
                  <span class="warehouse-panel__stat-label">Capacity</span>
                  <span class="warehouse-panel__stat-value">{{ active.capacitySqm.toLocaleString('en-US') }} m&sup2;</span>
                </div>
                <div class="warehouse-panel__stat">
                  <span class="warehouse-panel__stat-label">Utilization</span>
                  <span class="warehouse-panel__stat-value">{{ active.utilizationPercent }}%</span>
                </div>
                <div class="warehouse-panel__stat">
                  <span class="warehouse-panel__stat-label">Active Shipments</span>
                  <span class="warehouse-panel__stat-value">{{ active.activeShipments }}</span>
                </div>
                <div class="warehouse-panel__stat">
                  <span class="warehouse-panel__stat-label">Staff on Site</span>
                  <span class="warehouse-panel__stat-value">{{ active.staff }}</span>
                </div>
                <div class="warehouse-panel__stat">
                  <span class="warehouse-panel__stat-label">Couriers</span>
                  <span class="warehouse-panel__stat-value">{{ active.couriers }}</span>
                </div>
                <div class="warehouse-panel__stat">
                  <span class="warehouse-panel__stat-label">Avg. Courier KPI</span>
                  <span class="warehouse-panel__stat-value">{{ active.avgCourierKpi }}%</span>
                </div>
                <div class="warehouse-panel__stat">
                  <span class="warehouse-panel__stat-label">Courier Load</span>
                  <span class="warehouse-panel__stat-value">{{ active.courierLoadPercent }}%</span>
                </div>
                <div class="warehouse-panel__stat">
                  <span class="warehouse-panel__stat-label">Next Month Demand</span>
                  <span class="warehouse-panel__stat-value">{{ active.nextMonthDemand }}</span>
                </div>
              </div>
            </AccordionContent>
          </AccordionPanel>

          <AccordionPanel value="ai">
            <AccordionHeader>AI Suggestions</AccordionHeader>
            <AccordionContent>
              <WarehouseAiSuggestions
                :key="active.name"
                :store-id="active.storeId"
                :is-open="accordionValue === 'ai'"
              />
            </AccordionContent>
          </AccordionPanel>

          <AccordionPanel value="manage">
            <AccordionHeader>Manage</AccordionHeader>
            <AccordionContent>
              <WarehouseManageActions :key="active.name" :warehouse-name="active.name" />
            </AccordionContent>
          </AccordionPanel>

          <AccordionPanel value="trend">
            <AccordionHeader>Demand Trend</AccordionHeader>
            <AccordionContent>
              <Tabs value="monthly" class="warehouse-panel__tabs">
                <TabList>
                  <Tab value="monthly">Monthly</Tab>
                  <Tab value="daily">Daily</Tab>
                  <Tab value="hourly">Hourly</Tab>
                </TabList>
                <TabPanels>
                  <TabPanel value="monthly">
                    <div class="warehouse-panel__chart">
                      <Chart type="line" :data="chartData" :options="chartOptions" />
                    </div>
                  </TabPanel>
                  <TabPanel value="daily">
                    <DemandCalendar :store-id="active.storeId" />
                  </TabPanel>
                  <TabPanel value="hourly">
                    <DemandHourlyChart :warehouse-name="active.name" />
                  </TabPanel>
                </TabPanels>
              </Tabs>
            </AccordionContent>
          </AccordionPanel>
        </Accordion>
      </div>
    </Transition>
  </aside>
</template>

<style scoped>
.warehouse-panel {
  position: relative;
  z-index: 5;
  width: 27rem;
  flex-shrink: 0;
  height: 100%;
  background: var(--p-content-background);
  border-right: 1px solid var(--p-content-border-color);
  overflow: hidden;
}

.warehouse-panel__pane {
  position: absolute;
  inset: 0;
  overflow-y: auto;
  padding: 1.5rem 1.25rem;
  box-sizing: border-box;
  background: var(--p-content-background);
}

.slide-fwd-enter-active,
.slide-fwd-leave-active,
.slide-back-enter-active,
.slide-back-leave-active {
  transition: transform 0.28s ease;
}

.slide-fwd-enter-from {
  transform: translateX(100%);
}

.slide-fwd-leave-to {
  transform: translateX(-100%);
}

.slide-back-enter-from {
  transform: translateX(-100%);
}

.slide-back-leave-to {
  transform: translateX(100%);
}

.warehouse-panel__header {
  padding-bottom: 1.1rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.warehouse-panel__eyebrow {
  display: block;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--brand-blue);
}

.warehouse-panel__title {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--p-text-color);
  letter-spacing: -0.01em;
  line-height: 1.25;
}

.warehouse-panel__zone {
  font-size: 0.82rem;
  color: var(--p-text-muted-color);
}

.warehouse-panel__title-row {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  margin: 0.2rem 0 0.15rem;
}

.warehouse-panel__reset.p-button {
  padding: 0;
  width: 1.6rem;
  height: 1.6rem;
  flex-shrink: 0;
  color: var(--p-text-muted-color);
}

.warehouse-panel__health {
  margin-top: 1.1rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--p-content-border-color);
}

.warehouse-panel__health-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.warehouse-panel__health-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}

.warehouse-panel__health-value {
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.warehouse-panel__health-bar.p-progressbar {
  height: 8px;
  border-radius: 999px;
  background: var(--p-surface-200);
  margin-top: 0.5rem;
}

.warehouse-panel__health-bar :deep(.p-progressbar-value) {
  background: var(--health-color);
  border-radius: 999px;
}

.warehouse-panel__health-caption {
  display: block;
  margin-top: 0.45rem;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
}

.warehouse-panel__stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.1rem 1rem;
}

.warehouse-panel__stat {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.warehouse-panel__stat-label {
  font-size: 0.72rem;
  color: var(--p-text-muted-color);
}

.warehouse-panel__stat-value {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--p-text-color);
  letter-spacing: -0.01em;
}

.warehouse-panel__accordion {
  margin-top: 1.25rem;
}

.warehouse-panel__chart {
  height: 13rem;
}

.warehouse-panel__tabs.p-tabs :deep(.p-tablist-tab-list) {
  gap: 0.25rem;
}

.warehouse-panel__tabs.p-tabs :deep(.p-tabpanels) {
  padding: 1rem 0 0;
}

.warehouse-list__search {
  margin-top: 1.1rem;
}

.warehouse-list__search .p-inputtext {
  font-size: 0.85rem;
}

.warehouse-list__empty {
  margin: 1.5rem 0 0;
  font-size: 0.82rem;
  color: var(--p-text-muted-color);
  text-align: center;
}

.warehouse-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
  margin-top: 0.9rem;
}

.warehouse-list__item {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  padding: 0.85rem 0.95rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.7rem;
  background: transparent;
  font-family: var(--font-sans);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.warehouse-list__item:hover {
  border-color: var(--brand-blue);
  background: rgba(74, 125, 255, 0.06);
}

.warehouse-list__item-name {
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--p-text-color);
  letter-spacing: -0.01em;
}

.warehouse-list__item-zone {
  font-size: 0.78rem;
  color: var(--p-text-muted-color);
}

.warehouse-list__item-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.15rem;
}

.warehouse-list__item-metric {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.74rem;
  color: var(--p-text-muted-color);
}

.warehouse-list__item-metric .pi-circle-fill {
  font-size: 0.5rem;
}
</style>
