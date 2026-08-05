import { warehouses } from './warehouseData'

export type DemandLevel = 'low' | 'normal' | 'high' | 'critical'

export interface DayDemand {
  day: number
  value: number
  level: DemandLevel
}

// Default month shown when a branch's calendar first opens (today's
// context is Aug 2026), so it lines up with currentMonthDemand shown
// elsewhere. Chevron navigation can move away from this.
export const CALENDAR_YEAR = 2026
export const CALENDAR_MONTH = 7 // August, 0-indexed

export const DEMAND_LEVEL_LABEL: Record<DemandLevel, string> = {
  low: 'Below Normal',
  normal: 'Normal',
  high: 'Above Normal',
  critical: 'Critical',
}

function hashString(value: string): number {
  let h = 0
  for (let i = 0; i < value.length; i++) {
    h = (Math.imul(31, h) + value.charCodeAt(i)) | 0
  }
  return h
}

// Deterministic PRNG so a given branch/month combination always looks the
// same instead of reshuffling on every visit.
function mulberry32(seed: number) {
  let state = seed
  return () => {
    state |= 0
    state = (state + 0x6d2b79f5) | 0
    let t = Math.imul(state ^ (state >>> 15), 1 | state)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function classify(value: number, normal: number): DemandLevel {
  const ratio = value / normal
  if (ratio < 0.85) return 'low'
  if (ratio <= 1.15) return 'normal'
  if (ratio <= 1.4) return 'high'
  return 'critical'
}

// Generates a plausible day-by-day demand pattern for any given month,
// seeded by branch + year + month so navigating months/branches is stable
// and repeatable rather than random each time.
export function getDemandCalendarMonth(warehouseName: string, year: number, month: number): DayDemand[] {
  const props = warehouses.features.find((f) => f.properties.name === warehouseName)?.properties
  if (!props) return []

  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const normal = props.currentMonthDemand / daysInMonth
  const rand = mulberry32(hashString(`${warehouseName}|${year}-${month}`))
  // Branches already short on drivers trend hotter days more often, and
  // branches with headroom trend cooler - mirrors driverStatus instead of
  // contradicting it.
  const bias = props.driverStatus === 'shortage' ? 1.18 : props.driverStatus === 'surplus' ? 0.88 : 1.0

  const days: DayDemand[] = []
  for (let day = 1; day <= daysInMonth; day++) {
    let multiplier = bias + (rand() - 0.5) * 0.55
    if (rand() > 0.9) multiplier += 0.45
    const value = Math.max(0, Math.round(normal * multiplier))
    days.push({ day, value, level: classify(value, normal) })
  }
  return days
}

// Monthly total for the demand-chart markers - reuses the same daily
// generator (summed) so it's consistent with the calendar view and works
// for any month the user picks, not just the hand-authored trend range.
export function getMonthlyDemandTotal(warehouseName: string, year: number, month: number): number {
  return getDemandCalendarMonth(warehouseName, year, month).reduce((sum, d) => sum + d.value, 0)
}

export interface HourlyDemand {
  hour: number
  open: number
  high: number
  low: number
  close: number
}

// Relative intraday demand weight per hour - quiet overnight, ramping
// through the morning, peaking early afternoon.
const HOURLY_WEIGHTS = [
  0.2, 0.15, 0.1, 0.1, 0.15, 0.25, 0.45, 0.7, 0.9, 1.05, 1.15, 1.2, 1.25, 1.2, 1.15, 1.1, 1.05, 1.0, 0.85, 0.65, 0.5,
  0.4, 0.3, 0.25,
]
const HOURLY_PEAK_WEIGHT = Math.max(...HOURLY_WEIGHTS)

// A representative day's worth of hourly OHLC candles for a branch. Scaled
// off monthly demand (not divided down to a daily/hourly average, which
// would round every hour to 0-1) and shaped by the intraday curve above,
// normalized against its peak so the busiest hour lands near that peak
// value. Seeded by branch name so it's stable across renders.
export function getDemandHourlyData(warehouseName: string): HourlyDemand[] {
  const props = warehouses.features.find((f) => f.properties.name === warehouseName)?.properties
  if (!props) return []

  const hourlyPeak = props.currentMonthDemand / 8
  const rand = mulberry32(hashString(`${warehouseName}|hourly`))
  const bias = props.driverStatus === 'shortage' ? 1.12 : props.driverStatus === 'surplus' ? 0.92 : 1.0

  return HOURLY_WEIGHTS.map((weight, hour) => {
    const base = hourlyPeak * (weight / HOURLY_PEAK_WEIGHT) * bias
    const open = Math.max(0, base * (1 + (rand() - 0.5) * 0.35))
    const close = Math.max(0, base * (1 + (rand() - 0.5) * 0.35))
    const spread = base * 0.25 * rand()
    const high = Math.max(open, close) + spread
    const low = Math.max(0, Math.min(open, close) - spread)
    return {
      hour,
      open: Math.round(open),
      high: Math.round(high),
      low: Math.round(low),
      close: Math.round(close),
    }
  })
}
