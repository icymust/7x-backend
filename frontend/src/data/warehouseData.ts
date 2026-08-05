import type { Feature, FeatureCollection, Point } from 'geojson'
import { NETWORK_CENTER } from './mapData'
import {
  fetchLatestPlanRows,
  fetchStores,
  latestRowPerStore,
  type BackendPlanRow,
  type BackendStore,
} from '../services/warehousesApi'
import { hashString, mulberry32 } from '../utils/seededRandom'

export type WarehouseStatus = 'Operational' | 'Under Expansion' | 'Limited Capacity' | 'Unknown'

// Driver-capacity status: how courier headcount is tracking against the
// orders they're handling. Backend computes this now (aggregated across
// every day of the Planning Run: critical > shortage > surplus > balanced,
// see GET .../stores) - the value set matches BackendStoreStatus exactly, so
// it's used as-is rather than re-derived from a single day's snapshot.
export type DriverStatus = 'surplus' | 'balanced' | 'shortage' | 'critical'

export const DRIVER_STATUS_COLOR: Record<DriverStatus, string> = {
  surplus: '#16a34a',
  balanced: '#2563eb',
  shortage: '#eab308',
  critical: '#dc2626',
}

export const DRIVER_STATUS_LABEL: Record<DriverStatus, string> = {
  surplus: 'Driver Surplus',
  balanced: 'Balanced Capacity',
  shortage: 'High Utilization',
  critical: 'Driver Shortage',
}

export interface WarehouseProperties {
  // Backend's raw store_id - kept separate from the display `name` (which
  // may be a friendlier store_name) so other backend resources keyed by
  // store_id, like notifications, can be cross-referenced reliably.
  storeId: string
  name: string
  zone: string
  capacitySqm: number
  utilizationPercent: number
  activeShipments: number
  staff: number
  status: WarehouseStatus
  isMainBranch: boolean
  couriers: number
  avgCourierKpi: number
  courierLoadPercent: number
  driverStatus: DriverStatus
  currentMonthDemand: number
  nextMonthDemand: number
}

// Backend has no capacity/utilization/staff/courier-KPI concept at all yet -
// these two are seeded per store_id so they're stable across reloads and
// don't all look identical, but they are NOT real data. Everything else the
// backend genuinely lacks (see loadWarehouses()) is zeroed instead of faked.
function mockCapacitySqm(storeId: string): number {
  const rand = mulberry32(hashString(`${storeId}|capacity`))
  return Math.round((6000 + rand() * 26000) / 10) * 10
}

function mockAvgCourierKpi(storeId: string): number {
  const rand = mulberry32(hashString(`${storeId}|kpi`))
  return Math.round(78 + rand() * 17)
}

function courierLoadPercentFor(row: BackendPlanRow): number {
  if (row.required_courier_hours != null && row.available_courier_hours != null) {
    return row.available_courier_hours > 0
      ? Math.round((row.required_courier_hours / row.available_courier_hours) * 100)
      : 100
  }
  return row.available_couriers > 0
    ? Math.round((row.required_couriers / row.available_couriers) * 100)
    : 100
}

// `/stores` is the authoritative source for identity/coordinates/status;
// `/planning-runs/{id}` plan rows are the only source for courier counts.
// Merge them per store rather than picking one - each has data the other
// doesn't.
function toWarehouseFeature(store: BackendStore, latestRow: BackendPlanRow | undefined): Feature<Point, WarehouseProperties> {
  const courierLoadPercent = latestRow ? courierLoadPercentFor(latestRow) : 0
  // lat/lng are only null for a Planning Run created before the backend
  // started returning coordinates (see docs/ENDPOINTS.md "Warehouse map") -
  // falls back to [0, 0] for those, same as before.
  const coordinates: [number, number] =
    store.lat != null && store.lng != null ? [store.lng, store.lat] : [0, 0]

  return {
    type: 'Feature',
    geometry: { type: 'Point', coordinates },
    properties: {
      storeId: store.store_id,
      name: store.store_name ?? store.store_id,
      zone: latestRow?.zone ?? latestRow?.emirate ?? '',
      capacitySqm: mockCapacitySqm(store.store_id),
      utilizationPercent: 0,
      activeShipments: 0,
      staff: 0,
      status: 'Unknown',
      isMainBranch: false,
      couriers: latestRow ? latestRow.available_permanent + latestRow.available_outsourced : 0,
      avgCourierKpi: mockAvgCourierKpi(store.store_id),
      courierLoadPercent,
      driverStatus: store.status,
      currentMonthDemand: 0,
      nextMonthDemand: 0,
    },
  }
}

// A [0, 0] coordinate means the backend had no lat/lng for that store (see
// toWarehouseFeature) - not a real location, so map views that fit their
// bounds to the warehouse list should exclude it rather than let a single
// placeholder point collapse the bounds toward the Gulf of Guinea.
export function warehousesWithCoordinates(): Feature<Point, WarehouseProperties>[] {
  return warehouses.features.filter((f) => {
    const [lng, lat] = f.geometry.coordinates as [number, number]
    return !(lng === 0 && lat === 0)
  })
}

export const warehouses: FeatureCollection<Point, WarehouseProperties> = {
  type: 'FeatureCollection',
  features: [],
}

// Fallback for when the backend has no Planning Run yet (fresh DB, nothing
// uploaded) - keeps mainBranchWarehouse non-optional so every consumer
// doesn't need an undefined-check, at the cost of this one inert placeholder.
const EMPTY_WAREHOUSE: WarehouseProperties = {
  storeId: '',
  name: 'No warehouse data',
  zone: '',
  capacitySqm: 0,
  utilizationPercent: 0,
  activeShipments: 0,
  staff: 0,
  status: 'Unknown',
  isMainBranch: true,
  couriers: 0,
  avgCourierKpi: 0,
  courierLoadPercent: 0,
  driverStatus: 'surplus',
  currentMonthDemand: 0,
  nextMonthDemand: 0,
}

export let mainBranchWarehouse: WarehouseProperties = EMPTY_WAREHOUSE
export let mainBranchCoords: [number, number] = NETWORK_CENTER

// Fetches the latest Planning Run from the backend and populates `warehouses`
// in place. Call once at app startup (see main.ts) - components read
// `warehouses`/`mainBranchWarehouse`/`mainBranchCoords` synchronously, so
// this needs to resolve before the app mounts rather than be reactive.
export async function loadWarehouses(): Promise<void> {
  const [stores, rows] = await Promise.all([fetchStores(), fetchLatestPlanRows()])
  const latestRowByStore = new Map(latestRowPerStore(rows).map((row) => [row.store_id, row]))

  warehouses.features = stores.map((store) => toWarehouseFeature(store, latestRowByStore.get(store.store_id)))

  const mainFeature = warehouses.features[0]
  mainBranchWarehouse = mainFeature?.properties ?? EMPTY_WAREHOUSE
  mainBranchCoords = (mainFeature?.geometry.coordinates as [number, number] | undefined) ?? NETWORK_CENTER
}

export interface DemandHistoryPoint {
  month: string
  demand: number
  projected: boolean
}

// Trailing months of demand per branch for the details chart, ending on
// the current month, plus one forecast month. The last two entries always
// match currentMonthDemand/nextMonthDemand so the numbers agree everywhere
// on the card.
export const demandHistoryByWarehouse: Record<string, DemandHistoryPoint[]> = {
  'Mussafah Central Warehouse': months([350, 365, 380, 395, 405, 420, 460]),
  'ICAD 2 Logistics Park': months([340, 335, 325, 320, 315, 310, 295]),
  'ICAD 3 Distribution Hub': months([300, 320, 335, 350, 365, 380, 430]),
  'MBZ City Storage Facility': months([120, 128, 135, 140, 145, 150, 165]),
  'Al Falah Bulk Warehouse': months([70, 80, 88, 95, 102, 110, 140]),
  'Khalifa Port Free Zone Depot': months([580, 570, 560, 550, 545, 540, 505]),
  'Baniyas Cold Storage': months([80, 84, 87, 90, 93, 95, 100]),
}

function months(demand: number[]): DemandHistoryPoint[] {
  const labels = ['Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep']
  return demand.map((value, i) => ({
    month: labels[i],
    demand: value,
    projected: i === demand.length - 1,
  }))
}
