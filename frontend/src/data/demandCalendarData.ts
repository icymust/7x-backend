import { warehouses } from './warehouseData'
import { hashString, mulberry32 } from '../utils/seededRandom'

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
  const bias =
    props.driverStatus === 'critical'
      ? 1.3
      : props.driverStatus === 'shortage'
        ? 1.18
        : props.driverStatus === 'surplus'
          ? 0.88
          : 1.0

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
