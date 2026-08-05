<script setup lang="ts">
import { onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { LngLatBounds, Map as MapLibreMap, Marker } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useTheme } from '../composables/useTheme'
import { NETWORK_CENTER, NETWORK_DEFAULT_ZOOM } from '../data/mapData'
import { warehouses, warehousesWithCoordinates } from '../data/warehouseData'
import { loadWarehouseIcons } from '../utils/warehouseIcon'

const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'
const DARK_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

// Frames every warehouse regardless of the card's aspect ratio, rather
// than a fixed center/zoom that could crop pins in a short, wide card.
// Falls back to null when nothing has a real coordinate yet (see
// warehousesWithCoordinates) so the map keeps its static default view
// instead of fitting to a single [0, 0] point.
const locatedWarehouses = warehousesWithCoordinates()
const warehouseBounds =
  locatedWarehouses.length > 0
    ? locatedWarehouses.reduce(
        (bounds, f) => bounds.extend(f.geometry.coordinates as [number, number]),
        new LngLatBounds(),
      )
    : null

const { isDark } = useTheme()
const mapContainer = ref<HTMLDivElement>()
const map = shallowRef<MapLibreMap>()
let markers: Marker[] = []

async function addMarkers() {
  const m = map.value
  if (!m) return
  const icons = await loadWarehouseIcons()

  markers = warehouses.features.map((f) => {
    const el = document.createElement('img')
    el.src = icons[f.properties.driverStatus].src
    el.className = 'dashboard-mini-map__pin'
    return new Marker({ element: el, anchor: 'bottom' }).setLngLat(f.geometry.coordinates as [number, number]).addTo(m)
  })
}

function clearMarkers() {
  for (const marker of markers) marker.remove()
  markers = []
}

onMounted(() => {
  if (!mapContainer.value) return

  const m = new MapLibreMap({
    container: mapContainer.value,
    style: isDark.value ? DARK_STYLE : LIGHT_STYLE,
    center: NETWORK_CENTER,
    zoom: NETWORK_DEFAULT_ZOOM,
    // A static preview, not a real interactive map - clicks fall through
    // to the card underneath, which navigates to the full map page.
    interactive: false,
    attributionControl: false,
  })

  map.value = m
  m.on('load', () => {
    if (warehouseBounds) {
      m.fitBounds(warehouseBounds, { padding: 28, duration: 0, maxZoom: 13 })
    }
    addMarkers()
  })
})

onUnmounted(() => {
  clearMarkers()
  map.value?.remove()
})

watch(isDark, (dark) => {
  const m = map.value
  if (!m) return
  clearMarkers()
  m.setStyle(dark ? DARK_STYLE : LIGHT_STYLE)
  m.once('style.load', addMarkers)
})
</script>

<template>
  <div ref="mapContainer" class="dashboard-mini-map" />
</template>

<style scoped>
.dashboard-mini-map {
  position: absolute;
  inset: 0;
  overflow: hidden;
  border-radius: inherit;
  pointer-events: none;
}
</style>

<style>
/* Unscoped: MapLibre inserts marker elements outside this component's
   template, so scoped styles can't reach them. */
.dashboard-mini-map__pin {
  width: 22px;
  height: 22px;
  pointer-events: none;
}
</style>
