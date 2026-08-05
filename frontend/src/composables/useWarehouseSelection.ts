import { ref } from 'vue'
import type { WarehouseProperties } from '../data/warehouseData'
import { mainBranchCoords } from '../data/warehouseData'

// Shared between DemandMap (owns the actual map instance) and
// WarehousePanel (a sibling, not a child, now that the panel is a
// permanent column rather than an overlay rendered inside the map).
const selectedWarehouse = ref<WarehouseProperties | null>(null)
const focusTarget = ref<[number, number]>(mainBranchCoords)
// Bumped on every selection/reset so the map can watch for "please fly
// somewhere" even when the target coordinates repeat.
const focusToken = ref(0)
// Drives which view WarehousePanel renders: the full warehouse list, or the
// details of whichever warehouse was picked (from the list or the map).
const showList = ref(true)

function selectWarehouse(props: WarehouseProperties, coords: [number, number]) {
  selectedWarehouse.value = props
  focusTarget.value = coords
  focusToken.value++
  showList.value = false
}

function showWarehouseList() {
  showList.value = true
}

export function useWarehouseSelection() {
  return { selectedWarehouse, focusTarget, focusToken, showList, selectWarehouse, showWarehouseList }
}
