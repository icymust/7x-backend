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

// Fallback view for when there's no real warehouse data to fit bounds to yet
// (fresh DB, or a Planning Run predating coordinates). Calculated as the
// bounding-box midpoint of the current 10-store network (Abu Dhabi/Dubai/
// Sharjah): center = [(minLng+maxLng)/2, (minLat+maxLat)/2] over
// lng 54.362-55.3903, lat 24.477-25.3395. Zoom is a manual estimate sized to
// comfortably frame that ~100km x 96km spread with padding on a typical map
// card - maps that actually have warehouse data call fitBounds() instead of
// relying on this, so it self-corrects as the network grows or shifts.
export const NETWORK_CENTER: [number, number] = [54.876, 24.908]
export const NETWORK_DEFAULT_ZOOM = 9.5
