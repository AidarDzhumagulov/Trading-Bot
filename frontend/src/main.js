import { createApp } from 'vue'
import './style.css'
import router from "./router/index.js"
import App from './App.vue'

const app = createApp(App)

app.use(router)

app.mount('#app')