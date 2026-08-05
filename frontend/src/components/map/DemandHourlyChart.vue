<script setup lang="ts">
import { computed, ref } from 'vue'
import { getDemandHourlyData } from '../../data/demandCalendarData'

const props = defineProps<{ warehouseName: string }>()

const candles = computed(() => getDemandHourlyData(props.warehouseName))

// SVG is drawn in a 0-100 x 0-50 unit box so viewBox units line up 1:1
// with percentages - the same xFor()/VB_W math positions both the candle
// geometry and the HTML readout that floats above it.
const VB_W = 100
const VB_H = 50
const PAD_TOP = 4
const PAD_BOTTOM = 6

const maxHigh = computed(() => Math.max(...candles.value.map((c) => c.high), 1))
const minLow = computed(() => Math.min(...candles.value.map((c) => c.low), 0))

function yFor(value: number): number {
  const range = maxHigh.value - minLow.value || 1
  const t = (value - minLow.value) / range
  return VB_H - PAD_BOTTOM - t * (VB_H - PAD_TOP - PAD_BOTTOM)
}

const slotWidth = computed(() => VB_W / candles.value.length)

function xFor(i: number): number {
  return i * slotWidth.value + slotWidth.value / 2
}

function bodyY(open: number, close: number): number {
  return Math.min(yFor(open), yFor(close))
}

function bodyHeight(open: number, close: number): number {
  return Math.max(Math.abs(yFor(open) - yFor(close)), 0.6)
}

const hoveredHour = ref<number | null>(null)
const hovered = computed(() => (hoveredHour.value === null ? null : candles.value[hoveredHour.value]))
const readoutLeft = computed(() =>
  hoveredHour.value === null ? '0%' : `${(xFor(hoveredHour.value) / VB_W) * 100}%`,
)

function formatHour(hour: number): string {
  return new Date(2000, 0, 1, hour).toLocaleTimeString('en-US', { hour: 'numeric', hour12: true })
}
</script>

<template>
  <div class="hourly-chart">
    <div v-if="hovered" class="hourly-chart__readout" :style="{ left: readoutLeft }">
      <span class="hourly-chart__readout-hour">{{ formatHour(hovered.hour) }}</span>
      <span class="hourly-chart__readout-value">{{ hovered.close }}</span>
    </div>

    <svg
      class="hourly-chart__svg"
      :viewBox="`0 0 ${VB_W} ${VB_H}`"
      preserveAspectRatio="none"
      @mouseleave="hoveredHour = null"
    >
      <g
        v-for="(c, i) in candles"
        :key="c.hour"
        class="hourly-chart__candle"
        :class="[
          c.close >= c.open ? 'hourly-chart__candle--up' : 'hourly-chart__candle--down',
          { 'hourly-chart__candle--hovered': hoveredHour === i },
        ]"
        @mouseenter="hoveredHour = i"
      >
        <rect class="hourly-chart__highlight" :x="i * slotWidth" y="0" :width="slotWidth" :height="VB_H" />
        <line class="hourly-chart__wick" :x1="xFor(i)" :x2="xFor(i)" :y1="yFor(c.high)" :y2="yFor(c.low)" />
        <rect
          class="hourly-chart__body"
          :x="xFor(i) - slotWidth * 0.28"
          :y="bodyY(c.open, c.close)"
          :width="slotWidth * 0.56"
          :height="bodyHeight(c.open, c.close)"
        />
        <rect class="hourly-chart__hit" :x="i * slotWidth" y="0" :width="slotWidth" :height="VB_H" fill="transparent" />
      </g>
    </svg>

    <div class="hourly-chart__axis">
      <span v-for="h in [0, 6, 12, 18, 23]" :key="h">{{ formatHour(h) }}</span>
    </div>
  </div>
</template>

<style scoped>
.hourly-chart {
  position: relative;
  padding-top: 1.9rem;
}

.hourly-chart__readout {
  position: absolute;
  top: 0;
  transform: translateX(-50%);
  display: flex;
  align-items: baseline;
  gap: 0.35rem;
  padding: 0.2rem 0.5rem;
  border-radius: 0.4rem;
  background: var(--brand-navy);
  white-space: nowrap;
  pointer-events: none;
  z-index: 1;
}

.hourly-chart__readout-hour {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.65);
}

.hourly-chart__readout-value {
  font-size: 0.8rem;
  font-weight: 700;
  color: #ffffff;
}

.hourly-chart__svg {
  display: block;
  width: 100%;
  height: 11rem;
  overflow: visible;
}

.hourly-chart__highlight {
  fill: var(--brand-blue);
  opacity: 0;
  transition: opacity 0.1s ease;
}

.hourly-chart__candle--hovered .hourly-chart__highlight {
  opacity: 0.08;
}

.hourly-chart__wick {
  stroke: #16a34a;
  stroke-width: 0.35;
  vector-effect: non-scaling-stroke;
}

.hourly-chart__body {
  fill: #16a34a;
  transition: filter 0.1s ease;
}

.hourly-chart__candle--down .hourly-chart__wick {
  stroke: #dc2626;
}

.hourly-chart__candle--down .hourly-chart__body {
  fill: #dc2626;
}

.hourly-chart__candle--hovered .hourly-chart__body {
  filter: brightness(1.25);
}

.hourly-chart__hit {
  cursor: pointer;
}

.hourly-chart__axis {
  display: flex;
  justify-content: space-between;
  margin-top: 0.4rem;
  font-size: 0.68rem;
  color: var(--p-text-muted-color);
}
</style>
