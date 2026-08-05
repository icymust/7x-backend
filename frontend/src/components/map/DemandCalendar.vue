<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import Button from 'primevue/button'
import type { DayDemand } from '../../data/demandCalendarData'
import { CALENDAR_MONTH, CALENDAR_YEAR, DEMAND_LEVEL_LABEL, getDemandCalendarMonth } from '../../data/demandCalendarData'

const props = defineProps<{ warehouseName: string }>()

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const displayYear = ref(CALENDAR_YEAR)
const displayMonth = ref(CALENDAR_MONTH)

// Jumping to a different branch should land back on the default month
// rather than keep whatever month the previous branch was showing.
watch(
  () => props.warehouseName,
  () => {
    displayYear.value = CALENDAR_YEAR
    displayMonth.value = CALENDAR_MONTH
  },
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

const days = computed(() => getDemandCalendarMonth(props.warehouseName, displayYear.value, displayMonth.value))

const monthLabel = computed(() =>
  new Date(displayYear.value, displayMonth.value, 1).toLocaleDateString('en-US', { month: 'long', year: 'numeric' }),
)
const monthAbbrev = computed(() =>
  new Date(displayYear.value, displayMonth.value, 1).toLocaleDateString('en-US', { month: 'short' }),
)

// Pad the front of the grid with blanks so day 1 lands in its real weekday column.
const cells = computed<(DayDemand | null)[]>(() => {
  const firstWeekday = new Date(displayYear.value, displayMonth.value, 1).getDay()
  return [...Array(firstWeekday).fill(null), ...days.value]
})

const legendItems: { level: DayDemand['level']; label: string }[] = [
  { level: 'low', label: DEMAND_LEVEL_LABEL.low },
  { level: 'normal', label: DEMAND_LEVEL_LABEL.normal },
  { level: 'high', label: DEMAND_LEVEL_LABEL.high },
  { level: 'critical', label: DEMAND_LEVEL_LABEL.critical },
]
</script>

<template>
  <div class="demand-calendar">
    <div class="demand-calendar__nav">
      <Button icon="pi pi-chevron-left" text rounded size="small" aria-label="Previous month" @click="goToPrevMonth" />
      <span class="demand-calendar__month">{{ monthLabel }}</span>
      <Button icon="pi pi-chevron-right" text rounded size="small" aria-label="Next month" @click="goToNextMonth" />
    </div>

    <div class="demand-calendar__grid">
      <span v-for="wd in WEEKDAYS" :key="wd" class="demand-calendar__weekday">{{ wd }}</span>

      <div
        v-for="(cell, i) in cells"
        :key="i"
        class="demand-calendar__cell"
        :class="cell ? `demand-calendar__cell--${cell.level}` : 'demand-calendar__cell--empty'"
        :title="cell ? `${monthAbbrev} ${cell.day}: ${cell.value} orders (${DEMAND_LEVEL_LABEL[cell.level]})` : undefined"
      >
        <span v-if="cell" class="demand-calendar__day">{{ cell.day }}</span>
      </div>
    </div>

    <div class="demand-calendar__legend">
      <span v-for="item in legendItems" :key="item.level" class="demand-calendar__legend-item">
        <span class="demand-calendar__swatch" :class="`demand-calendar__cell--${item.level}`" />
        {{ item.label }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.demand-calendar {
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  margin-top: 0.9rem;
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
  aspect-ratio: 1;
  display: flex;
  align-items: flex-start;
  justify-content: flex-start;
  padding: 0.2rem;
  border-radius: 0.35rem;
  border: 1px solid var(--p-content-border-color);
}

.demand-calendar__cell--empty {
  border-color: transparent;
}

.demand-calendar__day {
  font-size: 0.6rem;
  font-weight: 600;
  color: var(--p-text-color);
}

.demand-calendar__cell--normal {
  background: var(--p-content-background);
}

.demand-calendar__cell--low {
  background: rgba(22, 163, 74, 0.18);
  border-color: rgba(22, 163, 74, 0.35);
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
