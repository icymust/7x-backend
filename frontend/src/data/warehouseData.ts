import type { FeatureCollection, Point } from 'geojson'

export type WarehouseStatus = 'Operational' | 'Under Expansion' | 'Limited Capacity'

// Driver-capacity status: how courier headcount is tracking against the
// orders they're handling. Derived from courierLoadPercent rather than
// hand-authored, so it can never drift out of sync with that number.
export type DriverStatus = 'surplus' | 'balanced' | 'shortage'

export const DRIVER_STATUS_COLOR: Record<DriverStatus, string> = {
  surplus: '#16a34a',
  balanced: '#d97706',
  shortage: '#dc2626',
}

export const DRIVER_STATUS_LABEL: Record<DriverStatus, string> = {
  surplus: 'Drivers Available',
  balanced: 'Drivers Stretched',
  shortage: 'Driver Shortage',
}

function computeDriverStatus(courierLoadPercent: number): DriverStatus {
  if (courierLoadPercent < 65) return 'surplus'
  if (courierLoadPercent <= 85) return 'balanced'
  return 'shortage'
}

export interface WarehouseProperties {
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

interface RawWarehouse {
  name: string
  zone: string
  capacitySqm: number
  utilizationPercent: number
  activeShipments: number
  staff: number
  status: WarehouseStatus
  isMainBranch?: boolean
  couriers: number
  avgCourierKpi: number
  courierLoadPercent: number
  currentMonthDemand: number
  nextMonthDemand: number
  coords: [number, number]
}

const rawWarehouses: RawWarehouse[] = [
  {
    name: 'Mussafah Central Warehouse',
    zone: 'ICAD 1',
    capacitySqm: 18000,
    utilizationPercent: 82,
    activeShipments: 46,
    staff: 128,
    status: 'Operational',
    isMainBranch: true,
    couriers: 42,
    avgCourierKpi: 91,
    courierLoadPercent: 78,
    currentMonthDemand: 420,
    nextMonthDemand: 460,
    coords: [54.498, 24.349],
  },
  {
    name: 'ICAD 2 Logistics Park',
    zone: 'ICAD 2',
    capacitySqm: 24500,
    utilizationPercent: 67,
    activeShipments: 38,
    staff: 94,
    status: 'Operational',
    couriers: 35,
    avgCourierKpi: 87,
    courierLoadPercent: 64,
    currentMonthDemand: 310,
    nextMonthDemand: 295,
    coords: [54.512, 24.331],
  },
  {
    name: 'ICAD 3 Distribution Hub',
    zone: 'ICAD 3',
    capacitySqm: 15200,
    utilizationPercent: 91,
    activeShipments: 52,
    staff: 76,
    status: 'Limited Capacity',
    couriers: 30,
    avgCourierKpi: 82,
    courierLoadPercent: 95,
    currentMonthDemand: 380,
    nextMonthDemand: 430,
    coords: [54.523, 24.317],
  },
  {
    name: 'MBZ City Storage Facility',
    zone: 'Mohammed Bin Zayed City',
    capacitySqm: 9800,
    utilizationPercent: 54,
    activeShipments: 19,
    staff: 41,
    status: 'Operational',
    couriers: 16,
    avgCourierKpi: 89,
    courierLoadPercent: 52,
    currentMonthDemand: 150,
    nextMonthDemand: 165,
    coords: [54.545, 24.322],
  },
  {
    name: 'Al Falah Bulk Warehouse',
    zone: 'Al Falah',
    capacitySqm: 12300,
    utilizationPercent: 48,
    activeShipments: 22,
    staff: 35,
    status: 'Under Expansion',
    couriers: 12,
    avgCourierKpi: 79,
    courierLoadPercent: 45,
    currentMonthDemand: 110,
    nextMonthDemand: 140,
    coords: [54.56, 24.4],
  },
  {
    name: 'Khalifa Port Free Zone Depot',
    zone: 'KPFZ',
    capacitySqm: 31000,
    utilizationPercent: 73,
    activeShipments: 64,
    staff: 152,
    status: 'Operational',
    couriers: 58,
    avgCourierKpi: 93,
    courierLoadPercent: 70,
    currentMonthDemand: 540,
    nextMonthDemand: 505,
    coords: [54.628, 24.52],
  },
  {
    name: 'Baniyas Cold Storage',
    zone: 'Baniyas Industrial',
    capacitySqm: 7600,
    utilizationPercent: 60,
    activeShipments: 14,
    staff: 28,
    status: 'Operational',
    couriers: 10,
    avgCourierKpi: 85,
    courierLoadPercent: 58,
    currentMonthDemand: 95,
    nextMonthDemand: 100,
    coords: [54.64, 24.336],
  },
]

export const warehouses: FeatureCollection<Point, WarehouseProperties> = {
  type: 'FeatureCollection',
  features: rawWarehouses.map((w) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: w.coords },
    properties: {
      name: w.name,
      zone: w.zone,
      capacitySqm: w.capacitySqm,
      utilizationPercent: w.utilizationPercent,
      activeShipments: w.activeShipments,
      staff: w.staff,
      status: w.status,
      isMainBranch: Boolean(w.isMainBranch),
      couriers: w.couriers,
      avgCourierKpi: w.avgCourierKpi,
      courierLoadPercent: w.courierLoadPercent,
      driverStatus: computeDriverStatus(w.courierLoadPercent),
      currentMonthDemand: w.currentMonthDemand,
      nextMonthDemand: w.nextMonthDemand,
    },
  })),
}

const mainBranchFeature = warehouses.features.find((f) => f.properties.isMainBranch)!
export const mainBranchWarehouse: WarehouseProperties = mainBranchFeature.properties
export const mainBranchCoords = mainBranchFeature.geometry.coordinates as [number, number]

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
