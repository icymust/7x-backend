<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import { fetchStoreCalendar, type CalendarDay, type CalendarSeverity } from '../../services/calendarApi'

const props = defineProps<{ storeId: string }>()

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

// Defaults to the current month rather than a fixed CALENDAR_YEAR/MONTH -
// the backend's calendar only has data from the Planning Run's
// planning_date forward (a future-forecast run has none before today), so
// starting anywhere else would just land on an empty month.
const today = new Date()
const displayYear = ref(today.getFullYear())
const displayMonth = ref(today.getMonth())

const loading = ref(false)
const error = ref<string | null>(null)
const days = ref<CalendarDay[]>([])

// Deliberately not toISOString(), which converts through UTC and can shift
// the date by a day in any timezone ahead of UTC.
function isoDate(year: number, month: number, day: number): string {
  return `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

async function loadMonth() {
  loading.value = true
  error.value = null
  try {
    const daysInMonth = new Date(displayYear.value, displayMonth.value + 1, 0).getDate()
    days.value = await fetchStoreCalendar(
      props.storeId,
      isoDate(displayYear.value, displayMonth.value, 1),
      isoDate(displayYear.value, displayMonth.value, daysInMonth),
    )
  } catch {
    error.value = 'Could not load calendar stats. Try again later.'
    days.value = []
  } finally {
    loading.value = false
  }
}

// Jumping to a different branch, or navigating months, both need a refetch
// - the backend has no client-side cache to fall back on.
watch(
  [() => props.storeId, displayYear, displayMonth],
  () => {
    loadMonth()
  },
  { immediate: true },
)

function goToPrevMonth() {
  if (displayMonth.value === 0) {
    displayMonth.value = 11
    displayYear.value -= 1
  } else {
    displayMonth.value -= 1
  }
}

function goToNextMonth() {
  if (displayMonth.value === 11) {
    displayMonth.value = 0
    displayYear.value += 1
  } else {
    displayMonth.value += 1
  }
}

const dayByDate = computed(() => new Map(days.value.map((d) => [d.date, d])))

const monthLabel = computed(() =>
  new Date(displayYear.value, displayMonth.value, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' }),
)
const monthAbbrev = computed(() =>
  new Date(displayYear.value, displayMonth.value, 1).toLocaleDateString('en-US', { month: 'short' }),
)

interface Cell {
  day: number
  data: CalendarDay | null
}

// Pad the front of the grid with blanks so day 1 lands in its real weekday
// column. Days the backend has no plan for (outside the Planning Run's
// horizon) still get a cell - just an empty one - so the grid shape never
// jumps around as you page through months.
const cells = computed<(Cell | null)[]>(() => {
  const firstWeekday = new Date(displayYear.value, displayMonth.value, 1).getDay()
  const daysInMonth = new Date(displayYear.value, displayMonth.value + 1, 0).getDate()
  const monthCells: Cell[] = Array.from({ length: daysInMonth }, (_, i) => {
    const day = i + 1
    return { day, data: dayByDate.value.get(isoDate(displayYear.value, displayMonth.value, day)) ?? null }
  })
  return [...Array(firstWeekday).fill(null), ...monthCells]
})

const SEVERITY_LABEL: Record<CalendarSeverity, string> = {
  critical: 'Critical shortage',
  high: 'High shortage',
  warning: 'Shortage',
  surplus: 'Surplus',
  normal: 'Balanced',
}

const legendItems: { severity: CalendarSeverity; label: string }[] = [
  { severity: 'surplus', label: SEVERITY_LABEL.surplus },
  { severity: 'normal', label: SEVERITY_LABEL.normal },
  { severity: 'warning', label: SEVERITY_LABEL.warning },
  { severity: 'high', label: SEVERITY_LABEL.high },
  { severity: 'critical', label: SEVERITY_LABEL.critical },
]

function cellTitle(day: number, data: CalendarDay): string {
  const orders = data.predicted_orders != null ? `${Math.round(data.predicted_orders)} orders` : null
  return [
    `${monthAbbrev.value} ${day}`,
    orders,
    `${data.coverage_percent}% coverage`,
    `shortage ${data.shortage_courier_slots}`,
    SEVERITY_LABEL[data.severity],
  ]
    .filter(Boolean)
    .join(' · ')
}

// Monthly stats for this store, built straight from the same rows behind
// the grid - critical-day count, average coverage and total shortage give
// a quick read on the month without having to scan every cell.
const stats = computed(() => {
  if (days.value.length === 0) return null

  const criticalDays = days.value.filter((d) => d.severity === 'critical').length
  const avgCoverage = days.value.reduce((sum, d) => sum + d.coverage_percent, 0) / days.value.length
  const totalShortage = days.value.reduce((sum, d) => sum + d.shortage_courier_slots, 0)
  const totalOrders = days.value.reduce((sum, d) => sum + (d.predicted_orders ?? 0), 0)

  return {
    criticalDays,
    avgCoverage: Math.round(avgCoverage * 10) / 10,
    totalShortage,
    totalOrders: Math.round(totalOrders),
  }
})
</script>

<template>
  <div class="demand-calendar">
    <div class="demand-calendar__nav">
      <Button icon="pi pi-chevron-left" text rounded size="small" aria-label="Previous month" @click="goToPrevMonth" />
      <span class="demand-calendar__month">{{ monthLabel }}</span>
      <Button icon="pi pi-chevron-right" text rounded size="small" aria-label="Next month" @click="goToNextMonth" />
    </div>

    <div v-if="loading" class="demand-calendar__status">Loading…</div>
    <p v-else-if="error" class="demand-calendar__status demand-calendar__status--error">{{ error }}</p>
    <template v-else>
      <div v-if="stats" class="demand-calendar__stats">
        <div class="demand-calendar__stat">
          <span class="demand-calendar__stat-value">{{ stats.avgCoverage }}%</span>
          <span class="demand-calendar__stat-label">Avg. Coverage</span>
        </div>
        <div class="demand-calendar__stat">
          <span class="demand-calendar__stat-value">{{ stats.criticalDays }}</span>
          <span class="demand-calendar__stat-label">Critical Days</span>
        </div>
        <div class="demand-calendar__stat">
          <span class="demand-calendar__stat-value">{{ stats.totalShortage }}</span>
          <span class="demand-calendar__stat-label">Shortage (couriers)</span>
        </div>
        <div class="demand-calendar__stat">
          <span class="demand-calendar__stat-value">{{ stats.totalOrders.toLocaleString('en-US') }}</span>
          <span class="demand-calendar__stat-label">Predicted Orders</span>
        </div>
      </div>
      <p v-else class="demand-calendar__status">No plan data for this month.</p>

      <div class="demand-calendar__grid" :key="`${displayYear}-${displayMonth}-${props.storeId}`">
        <span v-for="wd in WEEKDAYS" :key="wd" class="demand-calendar__weekday">{{ wd }}</span>

        <div
          v-for="(cell, i) in cells"
          :key="i"
          class="demand-calendar__cell"
          :class="cell ? `demand-calendar__cell--${cell.data?.severity ?? 'empty-data'}` : 'demand-calendar__cell--empty'"
          :style="{ '--cell-index': i }"
          :title="cell?.data ? cellTitle(cell.day, cell.data) : undefined"
        >
          <template v-if="cell">
            <span class="demand-calendar__day">{{ cell.day }}</span>
            <span v-if="cell.data?.predicted_orders != null" class="demand-calendar__count">
              {{ Math.round(cell.data.predicted_orders) }}
            </span>
          </template>
        </div>
      </div>

      <div class="demand-calendar__legend">
        <span v-for="item in legendItems" :key="item.severity" class="demand-calendar__legend-item">
          <span class="demand-calendar__swatch" :class="`demand-calendar__cell--${item.severity}`" />
          {{ item.label }}
        </span>
      </div>
    </template>
  </div>
</template>

<style scoped>
.demand-calendar {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin: 0.9rem auto 0;
  max-width: 20rem;
}

.demand-calendar__nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.demand-calendar__nav .p-button {
  width: 1.75rem;
  height: 1.75rem;
  color: var(--p-text-muted-color);
}

.demand-calendar__month {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--p-text-color);
}

.demand-calendar__status {
  margin: 0;
  padding: 0.75rem;
  font-size: 0.78rem;
  color: var(--p-text-muted-color);
  text-align: center;
}

.demand-calendar__status--error {
  color: #dc2626;
}

.demand-calendar__stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.6rem 0.75rem;
  padding: 0.7rem 0.8rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: 0.65rem;
  background: var(--p-content-background);
}

.demand-calendar__stat {
  display: flex;
  flex-direction: column;
  gap: 0.1rem;
}

.demand-calendar__stat-value {
  font-size: 1rem;
  font-weight: 700;
  color: var(--p-text-color);
  letter-spacing: -0.01em;
}

.demand-calendar__stat-label {
  font-size: 0.68rem;
  color: var(--p-text-muted-color);
}

.demand-calendar__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 0.25rem;
}

.demand-calendar__weekday {
  text-align: center;
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  color: var(--p-text-muted-color);
  padding-bottom: 0.15rem;
}

.demand-calendar__cell {
  position: relative;
  aspect-ratio: 1;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  padding: 0.2rem;
  border-radius: 0.35rem;
  border: 1px solid var(--p-content-border-color);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease;
  /* Staggered by --cell-index (set inline per cell) so the grid cascades in
     left-to-right, top-to-bottom instead of popping in all at once. Grid
     itself is keyed by year/month/store (and already unmounts/remounts via
     the loading v-if), so this replays on every navigation. */
  animation: demand-calendar-cell-in 0.36s ease backwards;
  animation-delay: calc(var(--cell-index, 0) * 10ms);
}

@keyframes demand-calendar-cell-in {
  from {
    opacity: 0;
    transform: translateY(5px) scale(0.9);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.demand-calendar__cell--empty,
.demand-calendar__cell--empty-data {
  border-color: transparent;
}

.demand-calendar__cell:not(.demand-calendar__cell--empty):hover {
  transform: scale(1.16);
  z-index: 2;
  box-shadow: 0 4px 10px rgba(15, 21, 32, 0.18);
  animation: demand-calendar-pulse 0.6s ease-out;
}

@keyframes demand-calendar-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(0, 32, 245, 0.45);
  }
  100% {
    box-shadow: 0 4px 10px rgba(15, 21, 32, 0.18);
  }
}

.demand-calendar__day {
  font-size: 0.6rem;
  font-weight: 600;
  color: var(--p-text-color);
  transition: opacity 0.15s ease;
}

.demand-calendar__cell:hover .demand-calendar__day {
  opacity: 0;
}

.demand-calendar__count {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--p-text-color);
  background: var(--p-content-background);
  border-radius: 0.3rem;
  opacity: 0;
  transform: scale(0.8);
  transition:
    opacity 0.15s ease,
    transform 0.15s ease;
  pointer-events: none;
}

.demand-calendar__cell:hover .demand-calendar__count {
  opacity: 1;
  transform: scale(1);
}

.demand-calendar__cell--normal {
  background: var(--p-content-background);
}

.demand-calendar__cell--surplus {
  background: rgba(22, 163, 74, 0.18);
  border-color: rgba(22, 163, 74, 0.35);
}

.demand-calendar__cell--warning {
  background: rgba(234, 179, 8, 0.2);
  border-color: rgba(234, 179, 8, 0.4);
}

.demand-calendar__cell--high {
  background: rgba(217, 119, 6, 0.2);
  border-color: rgba(217, 119, 6, 0.4);
}

.demand-calendar__cell--critical {
  background: rgba(220, 38, 38, 0.22);
  border-color: rgba(220, 38, 38, 0.45);
}

.demand-calendar__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
  margin-top: 0.15rem;
}

.demand-calendar__legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.7rem;
  color: var(--p-text-muted-color);
}

.demand-calendar__swatch {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 0.2rem;
  border: 1px solid var(--p-content-border-color);
  aspect-ratio: unset;
}
</style>
