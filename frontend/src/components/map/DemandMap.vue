<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  Popup,
  type ExpressionSpecification,
  type MapLayerMouseEvent,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import SelectButton from 'primevue/selectbutton'
import ToggleSwitch from 'primevue/toggleswitch'
import DatePicker from 'primevue/datepicker'
import { useTheme } from '../../composables/useTheme'
import { useWarehouseSelection } from '../../composables/useWarehouseSelection'
import { ABU_DHABI_CENTER, ABU_DHABI_ZOOM, demandPoints } from '../../data/mapData'
import type { DriverStatus, WarehouseProperties } from '../../data/warehouseData'
import { warehouses } from '../../data/warehouseData'
import { getMonthlyDemandTotal } from '../../data/demandCalendarData'
import { loadWarehouseIcons } from '../../utils/warehouseIcon'

const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const DARK_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const SOURCE_ID = 'demand-points'
const HEATMAP_LAYER = 'demand-heatmap'
const POINTS_LAYER = 'demand-points-circles'
const WAREHOUSE_SOURCE_ID = 'warehouses'
const WAREHOUSE_LAYER = 'warehouse-icons'
const DRIVER_STATUSES: DriverStatus[] = ['surplus', 'balanced', 'shortage', 'critical']
const FOCUS_ZOOM = 13.5

const { isDark } = useTheme()
const { selectWarehouse, focusTarget, focusToken } = useWarehouseSelection()

const mapContainer = ref<HTMLDivElement>()
const map = shallowRef<MapLibreMap>()

const viewModeOptions = ['Heatmap', 'Points']
const viewMode = ref<'Heatmap' | 'Points'>('Heatmap')
const showDemandChart = ref(false)
// Defaults to this month + next, matching what the card shows elsewhere,
// but the picker lets it range over any up to 4 months.
const selectedChartMonths = ref<Date[]>([new Date(2026, 7, 1), new Date(2026, 8, 1)])

function warehouseIconId(status: DriverStatus) {
  return `warehouse-icon-${status}`
}

const statusColorExpr: ExpressionSpecification = [
  'match',
  ['get', 'status'],
  'Open',
  '#0020F5',
  'Fulfilled',
  '#16a34a',
  'Pending',
  '#8b98a6',
  '#8b98a6',
]

async function addLayers() {
  const m = map.value
  if (!m) return

  if (!m.getSource(SOURCE_ID)) {
    m.addSource(SOURCE_ID, { type: 'geojson', data: demandPoints })
  }

  if (!m.getLayer(HEATMAP_LAYER)) {
    m.addLayer({
      id: HEATMAP_LAYER,
      type: 'heatmap',
      source: SOURCE_ID,
      paint: {
        'heatmap-weight': ['interpolate', ['linear'], ['get', 'requests'], 0, 0, 60, 1],
        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 9, 0.6, 14, 1.6],
        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 9, 14, 14, 34],
        'heatmap-opacity': 0.85,
        'heatmap-color': [
          'interpolate',
          ['linear'],
          ['heatmap-density'],
          0,
          'rgba(0,32,245,0)',
          0.2,
          'rgba(168,199,255,0.55)',
          0.5,
          'rgba(74,125,255,0.75)',
          0.8,
          'rgba(0,32,245,0.85)',
          1,
          'rgba(0,12,96,0.9)',
        ],
      },
    })
  }

  if (!m.getLayer(POINTS_LAYER)) {
    m.addLayer({
      id: POINTS_LAYER,
      type: 'circle',
      source: SOURCE_ID,
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['get', 'requests'], 8, 6, 60, 20],
        'circle-color': statusColorExpr,
        'circle-opacity': 0.88,
        'circle-stroke-width': 1.5,
        'circle-stroke-color': 'rgba(255,255,255,0.85)',
      },
    })

    m.on('click', POINTS_LAYER, (e: MapLayerMouseEvent) => {
      const f = e.features?.[0]
      if (!f || f.geometry.type !== 'Point') return
      const p = f.properties as { name: string; role: string; requests: number; status: string }
      new Popup({ closeButton: false, offset: 12 })
        .setLngLat(f.geometry.coordinates as [number, number])
        .setHTML(
          `<div style="font-family:'Noto Sans',sans-serif;font-size:0.8rem;line-height:1.4;color:#1B2333">
            <strong>${p.name}</strong><br/>
            ${p.role}<br/>
            ${p.requests} requests &middot; ${p.status}
          </div>`,
        )
        .addTo(m)
    })

    m.on('mouseenter', POINTS_LAYER, () => (m.getCanvas().style.cursor = 'pointer'))
    m.on('mouseleave', POINTS_LAYER, () => (m.getCanvas().style.cursor = ''))
  }

  const icons = await loadWarehouseIcons()
  for (const status of DRIVER_STATUSES) {
    if (!m.hasImage(warehouseIconId(status))) {
      m.addImage(warehouseIconId(status), icons[status], { pixelRatio: 2 })
    }
  }

  if (!m.getSource(WAREHOUSE_SOURCE_ID)) {
    m.addSource(WAREHOUSE_SOURCE_ID, { type: 'geojson', data: warehouses })
  }

  if (!m.getLayer(WAREHOUSE_LAYER)) {
    m.addLayer({
      id: WAREHOUSE_LAYER,
      type: 'symbol',
      source: WAREHOUSE_SOURCE_ID,
      layout: {
        'icon-image': [
          'match',
          ['get', 'driverStatus'],
          'surplus',
          warehouseIconId('surplus'),
          'balanced',
          warehouseIconId('balanced'),
          'shortage',
          warehouseIconId('shortage'),
          'critical',
          warehouseIconId('critical'),
          warehouseIconId('balanced'),
        ],
        'icon-size': 0.65,
        'icon-anchor': 'bottom',
        'icon-allow-overlap': true,
      },
    })

    m.on('click', WAREHOUSE_LAYER, (e: MapLayerMouseEvent) => {
      const f = e.features?.[0]
      if (!f || f.geometry.type !== 'Point') return
      selectWarehouse(f.properties as unknown as WarehouseProperties, f.geometry.coordinates as [number, number])
    })

    m.on('mouseenter', WAREHOUSE_LAYER, () => (m.getCanvas().style.cursor = 'pointer'))
    m.on('mouseleave', WAREHOUSE_LAYER, () => (m.getCanvas().style.cursor = ''))
  }

  applyVisibility()
}

function applyVisibility() {
  const m = map.value
  if (!m || !m.getLayer(HEATMAP_LAYER) || !m.getLayer(POINTS_LAYER)) return
  m.setLayoutProperty(HEATMAP_LAYER, 'visibility', viewMode.value === 'Heatmap' ? 'visible' : 'none')
  m.setLayoutProperty(POINTS_LAYER, 'visibility', viewMode.value === 'Points' ? 'visible' : 'none')
}

function focusOn(center: [number, number]) {
  map.value?.flyTo({ center, zoom: FOCUS_ZOOM, speed: 0.9, curve: 1.3, essential: true })
}

// The warehouse panel lives outside this component now (a sibling column,
// not an overlay rendered here), so selecting a branch there can't call
// focusOn directly - it bumps focusToken via the shared composable instead,
// and this is what actually flies the camera.
watch(focusToken, () => focusOn(focusTarget.value))

// Two-bar "this month vs. next month" demand chart, rendered as plain HTML
// markers rather than a GL layer - bars need independent, data-driven
// heights per branch, which is far simpler to express as DOM elements than
// as map-style paint expressions. Built once and toggled on/off, so it
// costs nothing while hidden.
const MAX_BAR_HEIGHT = 54

function monthLabel(date: Date) {
  return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
}

// Renders up to 4 bars for whichever months are currently picked, scaled
// against each other (not a fixed global max, since the picked months
// differ per user and can range across any year).
function renderDemandChartBars(el: HTMLDivElement, warehouseName: string) {
  const bars = el.querySelector('.demand-chart-marker__bars')
  if (!bars) return

  const months = selectedChartMonths.value
  const values = months.map((d) => getMonthlyDemandTotal(warehouseName, d.getFullYear(), d.getMonth()))
  const max = Math.max(1, ...values)

  bars.innerHTML = values
    .map((value, i) => {
      const height = Math.max(3, Math.round((value / max) * MAX_BAR_HEIGHT))
      return `<div class="demand-chart-marker__bar" style="height:${height}px" title="${warehouseName} - ${monthLabel(months[i])}: ${value}"></div>`
    })
    .join('')
}

function buildDemandChartEl(props: WarehouseProperties): HTMLDivElement {
  const el = document.createElement('div')
  el.className = 'demand-chart-marker'
  el.innerHTML = '<div class="demand-chart-marker__bars"></div>'
  renderDemandChartBars(el, props.name)

  el.addEventListener('click', () => {
    const feature = warehouses.features.find((f) => f.properties.name === props.name)
    if (feature) selectWarehouse(props, feature.geometry.coordinates as [number, number])
  })

  return el
}

let demandChartMarkers: Marker[] = []

function createDemandChartMarkers() {
  const m = map.value
  if (!m) return
  demandChartMarkers = warehouses.features.map((f) =>
    new Marker({ element: buildDemandChartEl(f.properties), anchor: 'bottom', offset: [0, -64] }).setLngLat(
      f.geometry.coordinates as [number, number],
    ),
  )
  applyDemandChartVisibility()
}

function applyDemandChartVisibility() {
  const m = map.value
  if (!m) return
  for (const marker of demandChartMarkers) {
    if (showDemandChart.value) marker.addTo(m)
    else marker.remove()
  }
}

// Markers are created once, in the same order as warehouses.features, so
// they can be zipped back together to refresh bar content in place instead
// of recreating the Marker instances whenever the month selection changes.
function refreshDemandChartContent() {
  demandChartMarkers.forEach((marker, i) => {
    const props = warehouses.features[i]?.properties
    if (props) renderDemandChartBars(marker.getElement() as HTMLDivElement, props.name)
  })
}

// MapLibre's own internal ResizeObserver (trackResize) redraws the canvas
// on every container-size notification with its own ~50ms throttle, which
// doesn't line up with the CSS transition's frame rate and reads as the
// map visually "shaking" while the sidebar collapses/expands. We disable
// that internal auto-resize once, up front, and instead drive resize()
// ourselves at most once per animation frame (rAF-throttled), so the
// content is redrawn in step with the browser's own paint cycle - smooth
// and continuous, matching the sidebar's transition, with no double work.
type MapWithTrackResize = MapLibreMap & { _trackResize: boolean }

let resizeObserver: ResizeObserver | undefined
let resizeFrame = 0

onMounted(() => {
  if (!mapContainer.value) return

  const m = new MapLibreMap({
    container: mapContainer.value,
    style: isDark.value ? DARK_STYLE : LIGHT_STYLE,
    center: ABU_DHABI_CENTER,
    zoom: ABU_DHABI_ZOOM,
  })

  m.addControl(new NavigationControl(), 'top-right')
  m.on('load', addLayers)
  map.value = m
  ;(m as MapWithTrackResize)._trackResize = false
  createDemandChartMarkers()

  resizeObserver = new ResizeObserver(() => {
    if (resizeFrame) return
    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = 0
      // resize() only updates the canvas's dimensions, which clears its
      // WebGL buffer immediately - the actual repaint is otherwise left
      // to MapLibre's own render loop on a later tick, so without forcing
      // it here too, each step briefly shows a blank/stale frame that
      // reads as the map's content "reloading". redraw() repaints
      // synchronously, right away, closing that gap.
      m.resize()
      m.redraw()
    })
  })
  resizeObserver.observe(mapContainer.value)
})

onUnmounted(() => {
  cancelAnimationFrame(resizeFrame)
  resizeObserver?.disconnect()
  for (const marker of demandChartMarkers) marker.remove()
  map.value?.remove()
})

watch(isDark, (dark) => {
  const m = map.value
  if (!m) return
  m.setStyle(dark ? DARK_STYLE : LIGHT_STYLE)
  m.once('style.load', addLayers)
})

watch(viewMode, applyVisibility)
watch(showDemandChart, applyDemandChartVisibility)
watch(selectedChartMonths, refreshDemandChartContent, { deep: true })
</script>

<template>
  <div class="demand-map">
    <div ref="mapContainer" class="demand-map__canvas" />

    <div class="demand-map__panel">
      <span class="demand-map__panel-label">View</span>
      <SelectButton
        v-model="viewMode"
        :options="viewModeOptions"
        :allow-empty="false"
        class="demand-map__view-toggle"
      />

      <span class="demand-map__panel-label">Insights</span>
      <label class="demand-map__warehouse-toggle">
        <ToggleSwitch v-model="showDemandChart" />
        <span>Monthly Demand Chart</span>
      </label>

      <template v-if="showDemandChart">
        <span class="demand-map__month-hint">Pick up to 4 months to compare</span>
        <DatePicker
          v-model="selectedChartMonths"
          selection-mode="multiple"
          view="month"
          date-format="M yy"
          :max-date-count="4"
          :manual-input="false"
          inline
          class="demand-map__month-picker"
        />
      </template>
    </div>
  </div>
</template>

<style scoped>
.demand-map {
  position: relative;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.demand-map__canvas {
  position: absolute;
  inset: 0;
}

.demand-map__panel {
  position: absolute;
  top: 1rem;
  left: 1rem;
  z-index: 10;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 1rem;
  width: 17rem;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.85rem;
  box-shadow: 0 8px 24px rgba(5, 9, 20, 0.16);
}

.demand-map__panel-label {
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
  margin-top: 0.35rem;
}

.demand-map__panel-label:first-child {
  margin-top: 0;
}

.demand-map__view-toggle {
  display: flex;
}

.demand-map__view-toggle :deep(.p-togglebutton) {
  flex: 1;
}

.demand-map__warehouse-toggle {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.85rem;
  color: var(--p-text-color);
  cursor: pointer;
}

.demand-map__month-hint {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  margin-top: -0.1rem;
}

.demand-map__month-picker.p-datepicker {
  width: 100%;
}

.demand-map__month-picker :deep(.p-datepicker-panel) {
  width: 100%;
  box-shadow: none;
  border: 1px solid var(--p-content-border-color);
}
</style>

<style>
/* Unscoped: MapLibre Markers insert these elements into its own overlay
   container, outside this component's template, so scoped styles can't
   reach them. */
.demand-chart-marker {
  display: flex;
  align-items: flex-end;
  gap: 7px;
  padding: 8px 10px 7px;
  background: var(--p-content-background);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  box-shadow: 0 3px 10px rgba(5, 9, 20, 0.2);
  cursor: pointer;
}

.demand-chart-marker__bars {
  display: flex;
  align-items: flex-end;
  gap: 7px;
}

.demand-chart-marker__bar {
  width: 13px;
  border-radius: 3px 3px 0 0;
  background: var(--p-primary-color);
}
</style>
