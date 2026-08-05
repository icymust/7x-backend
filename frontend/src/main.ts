import { createApp } from 'vue'
import PrimeVue from 'primevue/config'
import 'primeicons/primeicons.css'
import './style.css'
import App from './App.vue'
import { SevenXPreset } from './theme'
import { router } from './router'

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

app.mount('#app')
