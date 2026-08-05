export type NotificationStatus = 'success' | 'warning' | 'critical'

export const NOTIFICATION_STATUS_COLOR: Record<NotificationStatus, string> = {
  success: '#16a34a',
  warning: '#d97706',
  critical: '#dc2626',
}

export interface Notification {
  id: string
  title: string
  text: string
  status: NotificationStatus
  read: boolean
  timestamp: string
  // Name of the warehouse this notification is about, matching a name in
  // warehouseData.ts - lets the UI offer a "View Warehouse" deep link.
  // Omitted for notifications not tied to a specific branch (hiring, etc).
  warehouseName?: string
}

// Newest first - the dashboard card shows the first 4 as-is.
export const notifications: Notification[] = [
  {
    id: 'n1',
    title: 'Driver shortage at ICAD 3 Distribution Hub',
    text: 'Courier load has stayed above 95% for 3 consecutive days. Consider reallocating staff from a nearby branch.',
    status: 'critical',
    read: false,
    timestamp: '12m ago',
    warehouseName: 'ICAD 3 Distribution Hub',
  },
  {
    id: 'n2',
    title: 'Baniyas Cold Storage refrigeration alert',
    text: 'Temperature sensors flagged an anomaly in Zone B overnight. Maintenance has been dispatched.',
    status: 'critical',
    read: false,
    timestamp: '48m ago',
    warehouseName: 'Baniyas Cold Storage',
  },
  {
    id: 'n3',
    title: 'Khalifa Port Free Zone Depot nearing capacity',
    text: 'Utilization crossed 90% this week. Inbound shipments may need to be rerouted if the trend continues.',
    status: 'warning',
    read: false,
    timestamp: '3h ago',
    warehouseName: 'Khalifa Port Free Zone Depot',
  },
  {
    id: 'n4',
    title: '12 new hires completed onboarding',
    text: 'All Q3 candidates have cleared final training and are now active in the roster.',
    status: 'success',
    read: true,
    timestamp: '6h ago',
  },
  {
    id: 'n5',
    title: 'Al Falah Bulk Warehouse expansion delayed',
    text: 'The contractor has reported a 2-week delay on the new storage wing.',
    status: 'warning',
    read: false,
    timestamp: 'Yesterday',
    warehouseName: 'Al Falah Bulk Warehouse',
  },
  {
    id: 'n6',
    title: 'Mussafah Central Warehouse hit 100% on-time delivery',
    text: 'Zero late shipments were recorded across the branch this week.',
    status: 'success',
    read: true,
    timestamp: 'Yesterday',
    warehouseName: 'Mussafah Central Warehouse',
  },
  {
    id: 'n7',
    title: '163 candidates awaiting review',
    text: 'The Screened stage backlog has grown by 22 this week - pipeline may need more reviewers.',
    status: 'warning',
    read: true,
    timestamp: '2 days ago',
  },
  {
    id: 'n8',
    title: 'New courier batch cleared KPI threshold',
    text: '35 couriers scored above a 90% average KPI this month, led by the Khalifa Port team.',
    status: 'success',
    read: true,
    timestamp: '3 days ago',
    warehouseName: 'Khalifa Port Free Zone Depot',
  },
]
