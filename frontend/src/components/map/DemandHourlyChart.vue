<script setup lang="ts">
import { computed } from 'vue'
import Chart from 'primevue/chart'
import { useTheme } from '../../composables/useTheme'
import { BRAND_COLORS } from '../../theme'
import { getDemandHourlyData } from '../../data/demandCalendarData'

const props = defineProps<{ warehouseName: string }>()

const { isDark } = useTheme()

const candles = computed(() => getDemandHourlyData(props.warehouseName))

function formatHour(hour: number): string {
  return new Date(2000, 0, 1, hour).toLocaleTimeString('en-US', { hour: 'numeric', hour12: true })
}

// Only these hours get an axis label - printing all 24 would collide.
const AXIS_HOURS = [0, 6, 12, 18, 23]

const chartData = computed(() => {
  const barColor = isDark.value ? '#6B8FE0' : '#8CA9E8'
  return {
    labels: candles.value.map((c) => formatHour(c.hour)),
    datasets: [
      {
        data: candles.value.map((c) => Math.round(c.close)),
        backgroundColor: barColor,
        hoverBackgroundColor: isDark.value ? '#83A2E8' : '#6B8FE0',
        borderRadius: { topLeft: 3, topRight: 3, bottomLeft: 0, bottomRight: 0 },
        borderSkipped: false,
        categoryPercentage: 0.85,
        barPercentage: 0.85,
      },
    ],
  }
})

const chartOptions = computed(() => {
  const gridColor = isDark.value ? 'rgba(255,255,255,0.08)' : 'rgba(15,21,32,0.06)'
  const textColor = isDark.value ? 'rgba(255,255,255,0.65)' : 'rgba(15,21,32,0.55)'
  return {
    maintainAspectRatio: false,
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: BRAND_COLORS.navy,
        titleColor: 'rgba(255,255,255,0.65)',
        bodyColor: '#ffffff',
        bodyFont: { weight: 700 },
        padding: 8,
        cornerRadius: 6,
        displayColors: false,
        callbacks: {
          title: (items: { label: string }[]) => items[0].label,
          label: (ctx: { parsed: { y: number } }) => `${ctx.parsed.y} orders`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: {
          color: textColor,
          font: { size: 10 },
          autoSkip: false,
          callback: (_value: number, index: number) => (AXIS_HOURS.includes(index) ? formatHour(index) : null),
        },
      },
      y: {
        beginAtZero: true,
        grid: { color: gridColor },
        ticks: { color: textColor, font: { size: 10 } },
      },
    },
  }
})
</script>

<template>
  <div class="hourly-chart">
    <Chart type="bar" :data="chartData" :options="chartOptions" />
  </div>
</template>

<style scoped>
.hourly-chart {
  height: 11rem;
  width: 100%;
  position: relative;
}

.hourly-chart :deep(.p-chart) {
  height: 100%;
  width: 100%;
}
</style>
