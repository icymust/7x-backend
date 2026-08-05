import { createRouter, createWebHistory } from 'vue-router'
import DashboardPage from '../pages/DashboardPage.vue'
import MapPage from '../pages/MapPage.vue'
import NotificationsPage from '../pages/NotificationsPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardPage },
    { path: '/map', name: 'map', component: MapPage },
    { path: '/notifications', name: 'notifications', component: NotificationsPage },
  ],
})
