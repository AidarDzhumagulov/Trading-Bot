<template>
  <div class="min-h-screen bg-slate-950 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <div class="bg-slate-900 border border-slate-800 rounded-lg p-8 shadow-xl">
        <!-- Header -->
        <div class="text-center mb-8">
          <div class="flex items-center justify-center gap-3 mb-2">
            <TrendingUpIcon class="w-10 h-10 text-emerald-500"/>
            <h1 class="text-3xl font-bold text-slate-100">DCA Bot</h1>
          </div>
          <p class="text-slate-400">Войдите в свой аккаунт</p>
        </div>

        <div v-if="errorMessage" class="mb-6 p-4 bg-red-900/30 border border-red-800 rounded-lg">
          <div class="flex items-start gap-3">
            <AlertOctagonIcon class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5"/>
            <p class="text-sm text-red-300">{{ errorMessage }}</p>
          </div>
        </div>

        <form @submit.prevent="handleLogin" class="space-y-6">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              Email
            </label>
            <input
                v-model="email"
                type="email"
                required
                placeholder="your@email.com"
                class="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              Пароль
            </label>
            <input
                v-model="password"
                type="password"
                required
                placeholder="••••••••"
                class="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
            />
          </div>

          <button
              type="submit"
              :disabled="isLoading"
              class="w-full px-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition flex items-center justify-center gap-2"
          >
            <RefreshCwIcon v-if="isLoading" class="w-5 h-5 animate-spin"/>
            <span>{{ isLoading ? 'Вход...' : 'Войти' }}</span>
          </button>
        </form>

        <div class="mt-6 text-center">
          <p class="text-sm text-slate-400">
            Нет аккаунта?
            <router-link to="/register" class="text-emerald-500 hover:text-emerald-400 font-semibold">
              Зарегистрироваться
            </router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {ref} from 'vue'
import {useRouter} from 'vue-router'
import {AlertOctagonIcon, RefreshCwIcon, TrendingUpIcon} from 'lucide-vue-next'
import {login} from "../services/auth.js"

const router = useRouter()

const email = ref('')
const password = ref('')
const isLoading = ref(false)
const errorMessage = ref('')

const handleLogin = async () => {
  isLoading.value = true
  errorMessage.value = ''

  try {
    await login(email.value, password.value)

    router.push('/dashboard')
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    isLoading.value = false
  }
}
</script>