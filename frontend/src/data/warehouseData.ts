import type { Feature, FeatureCollection, Point } from 'geojson'
import { ABU_DHABI_CENTER } from './mapData'
import { fetchLatestPlanRows, latestRowPerStore, type BackendPlanRow } from '../services/warehousesApi'
import { hashString, mulberry32 } from '../utils/seededRandom'

export type WarehouseStatus = 'Operational' | 'Under Expansion' | 'Limited Capacity' | 'Unknown'

// Driver-capacity status: how courier headcount is tracking against the
// orders they're handling. Derived from courierLoadPercent rather than
// hand-authored, so it can never drift out of sync with that number.
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

function computeDriverStatus(courierLoadPercent: number): DriverStatus {
  if (courierLoadPercent < 60) return 'surplus'
  if (courierLoadPercent <= 75) return 'balanced'
  if (courierLoadPercent <= 90) return 'shortage'
  return 'critical'
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

function toWarehouseFeature(row: BackendPlanRow): Feature<Point, WarehouseProperties> {
  const courierLoadPercent = courierLoadPercentFor(row)

  return {
    type: 'Feature',
    // Store_Metadata requires latitude/longitude on upload, but the backend
    // drops them before they reach any API response (verified against
    // capacity.py's plan-row builder and every test fixture) - so there's no
    // real coordinate to place on the map yet.
    geometry: { type: 'Point', coordinates: [0, 0] },
    properties: {
      storeId: row.store_id,
      name: row.store_name ?? row.store_id,
      zone: row.zone ?? row.emirate ?? '',
      capacitySqm: mockCapacitySqm(row.store_id),
      utilizationPercent: 0,
      activeShipments: 0,
      staff: 0,
      status: 'Unknown',
      isMainBranch: false,
      couriers: row.available_permanent + row.available_outsourced,
      avgCourierKpi: mockAvgCourierKpi(row.store_id),
      courierLoadPercent,
      driverStatus: computeDriverStatus(courierLoadPercent),
      currentMonthDemand: 0,
      nextMonthDemand: 0,
    },
  }
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
export let mainBranchCoords: [number, number] = ABU_DHABI_CENTER

// Fetches the latest Planning Run from the backend and populates `warehouses`
// in place. Call once at app startup (see main.ts) - components read
// `warehouses`/`mainBranchWarehouse`/`mainBranchCoords` synchronously, so
// this needs to resolve before the app mounts rather than be reactive.
export async function loadWarehouses(): Promise<void> {
  const rows = await fetchLatestPlanRows()
  const latestRows = latestRowPerStore(rows)

  warehouses.features = latestRows.map(toWarehouseFeature)

  const mainFeature = warehouses.features[0]
  mainBranchWarehouse = mainFeature?.properties ?? EMPTY_WAREHOUSE
  mainBranchCoords = (mainFeature?.geometry.coordinates as [number, number] | undefined) ?? ABU_DHABI_CENTER
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
