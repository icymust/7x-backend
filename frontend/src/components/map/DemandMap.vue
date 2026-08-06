<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import {
  LngLatBounds,
  Map as MapLibreMap,
  NavigationControl,
  type MapLayerMouseEvent,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useTheme } from '../../composables/useTheme'
import { useWarehouseSelection } from '../../composables/useWarehouseSelection'
import { NETWORK_CENTER, NETWORK_DEFAULT_ZOOM } from '../../data/mapData'
import type { DriverStatus, WarehouseProperties } from '../../data/warehouseData'
import { warehouses, warehousesWithCoordinates } from '../../data/warehouseData'
import { loadWarehouseIcons } from '../../utils/warehouseIcon'

const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const DARK_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
const WAREHOUSE_SOURCE_ID = 'warehouses'
const WAREHOUSE_LAYER = 'warehouse-icons'
const DRIVER_STATUSES: DriverStatus[] = ['surplus', 'balanced', 'shortage', 'critical']
const FOCUS_ZOOM = 13.5

const { isDark } = useTheme()
const { selectWarehouse, focusTarget, focusToken } = useWarehouseSelection()

const mapContainer = ref<HTMLDivElement>()
const map = shallowRef<MapLibreMap>()

function warehouseIconId(status: DriverStatus) {
  return `warehouse-icon-${status}`
}

async function addWarehouseLayer() {
  const currentMap = map.value
  if (!currentMap) return

  const icons = await loadWarehouseIcons()

  for (const status of DRIVER_STATUSES) {
    if (!currentMap.hasImage(warehouseIconId(status))) {
      currentMap.addImage(warehouseIconId(status), icons[status], { pixelRatio: 2 })
    }
  }

  if (!currentMap.getSource(WAREHOUSE_SOURCE_ID)) {
    currentMap.addSource(WAREHOUSE_SOURCE_ID, { type: 'geojson', data: warehouses })
  }

  if (currentMap.getLayer(WAREHOUSE_LAYER)) return

  currentMap.addLayer({
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

  currentMap.on('click', WAREHOUSE_LAYER, (event: MapLayerMouseEvent) => {
    const feature = event.features?.[0]
    if (!feature || feature.geometry.type !== 'Point') return

    selectWarehouse(
      feature.properties as unknown as WarehouseProperties,
      feature.geometry.coordinates as [number, number],
    )
  })

  currentMap.on('mouseenter', WAREHOUSE_LAYER, () => {
    currentMap.getCanvas().style.cursor = 'pointer'
  })
  currentMap.on('mouseleave', WAREHOUSE_LAYER, () => {
    currentMap.getCanvas().style.cursor = ''
  })
}

function focusOn(center: [number, number]) {
  map.value?.flyTo({
    center,
    zoom: FOCUS_ZOOM,
    speed: 0.9,
    curve: 1.3,
    essential: true,
  })
}

function fitToWarehouses() {
  const currentMap = map.value
  const located = warehousesWithCoordinates()
  if (!currentMap || located.length === 0) return

  const bounds = located.reduce(
    (currentBounds, feature) => currentBounds.extend(
      feature.geometry.coordinates as [number, number],
    ),
    new LngLatBounds(),
  )

  currentMap.fitBounds(bounds, {
    padding: 72,
    duration: 0,
    maxZoom: 13,
  })
}

watch(focusToken, () => focusOn(focusTarget.value))

type MapWithTrackResize = MapLibreMap & { _trackResize: boolean }

let resizeObserver: ResizeObserver | undefined
let resizeFrame = 0

onMounted(() => {
  if (!mapContainer.value) return

  const currentMap = new MapLibreMap({
    container: mapContainer.value,
    style: isDark.value ? DARK_STYLE : LIGHT_STYLE,
    center: NETWORK_CENTER,
    zoom: NETWORK_DEFAULT_ZOOM,
  })

  currentMap.addControl(new NavigationControl(), 'top-right')
  currentMap.on('load', () => {
    fitToWarehouses()
    addWarehouseLayer()
  })
  map.value = currentMap
  ;(currentMap as MapWithTrackResize)._trackResize = false

  resizeObserver = new ResizeObserver(() => {
    if (resizeFrame) return

    resizeFrame = requestAnimationFrame(() => {
      resizeFrame = 0
      currentMap.resize()
      currentMap.redraw()
    })
  })
  resizeObserver.observe(mapContainer.value)
})

onUnmounted(() => {
  cancelAnimationFrame(resizeFrame)
  resizeObserver?.disconnect()
  map.value?.remove()
})

watch(isDark, (dark) => {
  const currentMap = map.value
  if (!currentMap) return

  currentMap.setStyle(dark ? DARK_STYLE : LIGHT_STYLE)
  currentMap.once('style.load', addWarehouseLayer)
})
</script>

<template>
  <div class="demand-map">
    <div ref="mapContainer" class="demand-map__canvas" />
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
</style>
