import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import 'primeicons/primeicons.css'
import './style.css'
import App from './App.vue'
import { SevenXPreset } from './theme'
import { router } from './router'
import { loadWarehouses } from './data/warehouseData'
import { loadNotifications } from './data/notificationsData'

const app = createApp(App)

app.use(PrimeVue, {
  theme: {
    preset: SevenXPreset,
    options: {
      darkModeSelector: '.app-dark',
      cssLayer: false,
    },
  },
})

app.use(router)

// Components read this data synchronously (no loading states wired up yet),
// so both fetches have to resolve before the app mounts rather than run
// reactively in the background. Sequential, not parallel: notifications
// resolve each store_id to a warehouse name, which only works once
// `warehouses` is populated. Each has its own catch so one failing (backend
// down, no Planning Run yet) doesn't block the other or hang the app.
async function bootstrap() {
  await loadWarehouses().catch((error) => console.error('Failed to load warehouses', error))
  await loadNotifications().catch((error) => console.error('Failed to load notifications', error))
  app.mount('#app')
}

bootstrap()
