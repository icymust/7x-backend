export interface HiringStat {
  label: string
  value: string
  icon: string
  trend: string
  trendUp: boolean
}

export const hiringStats: HiringStat[] = [
  { label: 'Total Workforce', value: '544', icon: 'pi pi-users', trend: '+18 this month', trendUp: true },
  { label: 'Open Positions', value: '27', icon: 'pi pi-briefcase', trend: '+4 this week', trendUp: true },
  { label: 'Candidates in Pipeline', value: '163', icon: 'pi pi-id-card', trend: '+22 this week', trendUp: true },
  { label: 'Avg. Time to Hire', value: '14 days', icon: 'pi pi-clock', trend: '-2 days', trendUp: true },
]

export interface HiringStage {
  label: string
  count: number
}

export const hiringPipeline: HiringStage[] = [
  { label: 'Applied', count: 342 },
  { label: 'Screened', count: 168 },
  { label: 'Interviewed', count: 74 },
  { label: 'Offered', count: 21 },
  { label: 'Hired', count: 12 },
]
