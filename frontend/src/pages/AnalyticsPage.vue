<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import Chart from 'primevue/chart'
import { useTheme } from '../composables/useTheme'
import {
  fetchLatestDemandAnalytics,
  type DemandAnalyticsResponse,
} from '../services/analyticsApi'

const { isDark } = useTheme()
const analytics = ref<DemandAnalyticsResponse | null>(null)
const loading = ref(true)
const errorMessage = ref<string | null>(null)

const numberFormatter = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 0,
})

function formatOrders(value: number) {
  return numberFormatter.format(Math.round(value))
}

function formatMonth(value: string) {
  const [year, month] = value.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    year: 'numeric',
  }).format(new Date(year, month - 1, 1))
}

function formatDate(value: string) {
  const [year, month, day] = value.split('-').map(Number)
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
  }).format(new Date(year, month - 1, day))
}

const monthlyRows = computed(() => [
  ...(analytics.value?.historical_monthly ?? []),
  ...(analytics.value?.forecast_monthly ?? []),
].sort((left, right) => left.month.localeCompare(right.month)))

const chartData = computed(() => ({
  labels: monthlyRows.value.map((row) => formatMonth(row.month)),
  datasets: [
    {
      label: 'Actual orders',
      data: monthlyRows.value.map((row) => row.source === 'actual' ? row.orders : null),
      backgroundColor: isDark.value ? '#6B8FE0' : '#0020F5',
      borderRadius: 6,
      borderSkipped: false,
    },
    {
      label: 'ML forecast',
      data: monthlyRows.value.map((row) => row.source === 'ml_forecast' ? row.orders : null),
      backgroundColor: isDark.value ? '#49C5B6' : '#20A995',
      borderRadius: 6,
      borderSkipped: false,
    },
  ],
}))

const chartOptions = computed(() => {
  const gridColor = isDark.value ? 'rgba(255,255,255,0.08)' : 'rgba(15,21,32,0.07)'
  const textColor = isDark.value ? 'rgba(255,255,255,0.7)' : 'rgba(15,21,32,0.62)'

  return {
    maintainAspectRatio: false,
    responsive: true,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'top',
        align: 'end',
        labels: {
          color: textColor,
          boxWidth: 12,
          usePointStyle: true,
          pointStyle: 'circle',
        },
      },
      tooltip: {
        callbacks: {
          label: (context: { dataset: { label: string }; raw: number }) => (
            `${context.dataset.label}: ${formatOrders(context.raw)} orders`
          ),
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        grid: { display: false },
        ticks: { color: textColor },
      },
      y: {
        stacked: true,
        beginAtZero: true,
        grid: { color: gridColor },
        ticks: {
          color: textColor,
          callback: (value: number) => numberFormatter.format(value),
        },
      },
    },
  }
})

onMounted(async () => {
  try {
    analytics.value = await fetchLatestDemandAnalytics()

    if (analytics.value === null) {
      errorMessage.value = 'Upload and calculate a workforce workbook first.'
    }
  } catch (error) {
    console.error('Failed to load demand analytics', error)
    errorMessage.value = 'Demand analytics is unavailable. Recalculate the workbook with the latest backend.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="analytics">
    <div class="analytics__inner">
      <header class="analytics__header">
        <span class="analytics__eyebrow">Machine Learning</span>
        <h1 class="analytics__title">Demand Analytics</h1>
        <p class="analytics__subtitle">
          Historical actual orders compared with the next 90 days predicted by CatBoost.
        </p>
      </header>

      <div v-if="loading" class="analytics__state">
        <i class="pi pi-spin pi-spinner" /> Loading analytics...
      </div>

      <div v-else-if="errorMessage" class="analytics__state analytics__state--error">
        <i class="pi pi-exclamation-circle" /> {{ errorMessage }}
      </div>

      <template v-else-if="analytics">
        <section class="analytics__summary">
          <article class="analytics__metric">
            <span class="analytics__metric-label">Historical orders</span>
            <strong class="analytics__metric-value">
              {{ formatOrders(analytics.historical_total_orders) }}
            </strong>
            <span class="analytics__metric-note">Actual orders from Excel</span>
          </article>

          <article class="analytics__metric analytics__metric--forecast">
            <span class="analytics__metric-label">90-day forecast</span>
            <strong class="analytics__metric-value">
              {{ formatOrders(analytics.forecast_total_orders) }}
            </strong>
            <span class="analytics__metric-note">Predicted by {{ analytics.model_version }}</span>
          </article>
        </section>

        <section class="analytics__card analytics__chart-card">
          <div class="analytics__card-heading">
            <div>
              <h2>Monthly order volume</h2>
              <p>Blue bars are actual data; green bars are the ML forecast.</p>
            </div>
          </div>
          <div class="analytics__chart">
            <Chart type="bar" :data="chartData" :options="chartOptions" />
          </div>
        </section>

        <section class="analytics__card">
          <div class="analytics__card-heading">
            <div>
              <h2>Monthly breakdown</h2>
              <p>Partial forecast months show the exact number of covered days.</p>
            </div>
          </div>

          <div class="analytics__table-wrap">
            <table class="analytics__table">
              <thead>
                <tr>
                  <th>Month</th>
                  <th>Source</th>
                  <th>Covered period</th>
                  <th>Days</th>
                  <th>Total orders</th>
                  <th>Average / day</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in monthlyRows" :key="`${row.source}-${row.month}`">
                  <td><strong>{{ formatMonth(row.month) }}</strong></td>
                  <td>
                    <span class="analytics__source" :class="`analytics__source--${row.source}`">
                      {{ row.source === 'actual' ? 'Actual' : 'ML forecast' }}
                    </span>
                  </td>
                  <td>{{ formatDate(row.date_from) }} – {{ formatDate(row.date_to) }}</td>
                  <td>{{ row.covered_days }}</td>
                  <td><strong>{{ formatOrders(row.orders) }}</strong></td>
                  <td>{{ formatOrders(row.average_orders_per_day) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </template>
    </div>
  </div>
</template>

<style scoped>
.analytics {
  flex: 1;
  min-width: 0;
  height: 100%;
  overflow-y: auto;
}

.analytics__inner {
  max-width: 78rem;
  margin: 0 auto;
  padding: 1.5rem 2.25rem 3rem;
}

.analytics__header {
  margin-bottom: 1.25rem;
}

.analytics__eyebrow {
  display: block;
  color: var(--brand-blue);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.analytics__title {
  margin: 0.15rem 0 0.25rem;
  color: var(--p-text-color);
  font-size: 2rem;
  letter-spacing: -0.01em;
}

.analytics__subtitle,
.analytics__card-heading p,
.analytics__metric-note {
  color: var(--p-text-muted-color);
}

.analytics__subtitle,
.analytics__card-heading p {
  margin: 0;
  font-size: 0.85rem;
}

.analytics__summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
  margin-bottom: 0.75rem;
}

.analytics__metric,
.analytics__card {
  border: 1px solid var(--p-content-border-color);
  background: var(--p-content-background);
  border-radius: 1rem;
}

.analytics__metric {
  position: relative;
  padding: 1.1rem 1.25rem;
  overflow: hidden;
}

.analytics__metric::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: var(--brand-blue);
  content: '';
}

.analytics__metric--forecast::before {
  background: #20a995;
}

.analytics__metric-label,
.analytics__metric-note {
  display: block;
}

.analytics__metric-label {
  font-size: 0.78rem;
  font-weight: 600;
}

.analytics__metric-value {
  display: block;
  margin: 0.2rem 0;
  color: var(--p-text-color);
  font-size: 1.7rem;
}

.analytics__metric-note {
  font-size: 0.72rem;
}

.analytics__card {
  padding: 1.15rem 1.25rem;
  margin-bottom: 0.75rem;
}

.analytics__card-heading h2 {
  margin: 0 0 0.2rem;
  color: var(--p-text-color);
  font-size: 1rem;
}

.analytics__chart {
  height: 20rem;
  margin-top: 0.6rem;
}

.analytics__table-wrap {
  margin-top: 1rem;
  overflow-x: auto;
}

.analytics__table {
  width: 100%;
  border-collapse: collapse;
  color: var(--p-text-color);
  font-size: 0.82rem;
}

.analytics__table th,
.analytics__table td {
  padding: 0.8rem 0.7rem;
  border-bottom: 1px solid var(--p-content-border-color);
  text-align: left;
  white-space: nowrap;
}

.analytics__table th {
  color: var(--p-text-muted-color);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.analytics__source {
  display: inline-flex;
  padding: 0.25rem 0.5rem;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 700;
}

.analytics__source--actual {
  color: #214ec4;
  background: rgba(74, 125, 255, 0.14);
}

.analytics__source--ml_forecast {
  color: #087765;
  background: rgba(32, 169, 149, 0.14);
}

.analytics__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  min-height: 16rem;
  border: 1px solid var(--p-content-border-color);
  border-radius: 1rem;
  color: var(--p-text-muted-color);
  background: var(--p-content-background);
}

.analytics__state--error {
  color: var(--p-red-500);
}

@media (max-width: 700px) {
  .analytics__inner {
    padding: 1.25rem 1rem 2rem;
  }

  .analytics__summary {
    grid-template-columns: 1fr;
  }
}
</style>
