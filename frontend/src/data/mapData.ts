import type { FeatureCollection, Point } from 'geojson'

export type RequestStatus = 'Open' | 'Fulfilled' | 'Pending'

export interface DemandPointProperties {
  name: string
  role: string
  requests: number
  status: RequestStatus
}


interface RawDemandPoint {
  name: string
  role: string
  requests: number
  status: RequestStatus
  coords: [number, number]
}

const rawDemandPoints: RawDemandPoint[] = [
  { name: 'Al Markaziyah (Downtown)', role: 'Warehouse Operator', requests: 42, status: 'Open', coords: [54.3705, 24.4764] },
  { name: 'Corniche', role: 'Delivery Driver', requests: 18, status: 'Fulfilled', coords: [54.33, 24.47] },
  { name: 'Al Bateen', role: 'Electrician', requests: 12, status: 'Pending', coords: [54.333, 24.455] },
  { name: 'Al Reem Island', role: 'Warehouse Operator', requests: 27, status: 'Open', coords: [54.402, 24.499] },
  { name: 'Saadiyat Island', role: 'Electrician', requests: 9, status: 'Fulfilled', coords: [54.431, 24.547] },
  { name: 'Yas Island', role: 'Forklift Driver', requests: 31, status: 'Open', coords: [54.605, 24.488] },
  { name: 'Khalifa City', role: 'Delivery Driver', requests: 24, status: 'Pending', coords: [54.596, 24.423] },
  { name: 'Mussafah', role: 'Welder', requests: 56, status: 'Open', coords: [54.493, 24.345] },
  { name: 'Mohammed Bin Zayed City', role: 'Warehouse Operator', requests: 33, status: 'Open', coords: [54.539, 24.323] },
  { name: 'Baniyas', role: 'Forklift Driver', requests: 15, status: 'Fulfilled', coords: [54.633, 24.333] },
  { name: 'Al Shahama', role: 'Welder', requests: 11, status: 'Pending', coords: [54.598, 24.379] },
  { name: 'Al Zahiyah', role: 'Delivery Driver', requests: 19, status: 'Open', coords: [54.363, 24.487] },
]

export const demandPoints: FeatureCollection<Point, DemandPointProperties> = {
  type: 'FeatureCollection',
  features: rawDemandPoints.map((p) => ({
    type: 'Feature',
    geometry: { type: 'Point', coordinates: p.coords },
    properties: { name: p.name, role: p.role, requests: p.requests, status: p.status },
  })),
}

// City-wide view: downtown Abu Dhabi, zoomed to frame the whole emirate's urban area.
export const ABU_DHABI_CENTER: [number, number] = [54.3705, 24.4764]
export const ABU_DHABI_ZOOM = 11
