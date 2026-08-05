export interface HiringStat {
  label: string
  value: string
  icon: string
  trend: string
  trendUp: boolean
}

export const hiringStats: HiringStat[] = [
  { label: 'Total Workforce', value: '544', icon: 'pi pi-users', trend: '+18 this month', trendUp: true },
  { label: "Drivers' KPI", value: '87%', icon: 'pi pi-gauge', trend: '+3% this month', trendUp: true },
  { label: 'Parcels Last Month', value: '8,420', icon: 'pi pi-box', trend: '+9% vs prior month', trendUp: true },
  { label: 'Avg. Time to Hire', value: '14 days', icon: 'pi pi-clock', trend: '-2 days', trendUp: true },
]
