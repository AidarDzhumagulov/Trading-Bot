<template>
  <div class="min-h-screen bg-slate-950 flex items-center justify-center p-4">
    <div class="w-full max-w-md">
      <div
        class="bg-slate-900 border border-slate-800 rounded-lg p-8 shadow-xl"
      >
        <div class="text-center mb-8">
          <div class="flex items-center justify-center gap-3 mb-2">
            <TrendingUpIcon class="w-10 h-10 text-emerald-500" />
            <h1 class="text-3xl font-bold text-slate-100">DCA Bot</h1>
          </div>
          <p class="text-slate-400">Создайте новый аккаунт</p>
        </div>

        <div
          v-if="errorMessage"
          class="mb-6 p-4 bg-red-900/30 border border-red-800 rounded-lg"
        >
          <div class="flex items-start gap-3">
            <AlertOctagonIcon
              class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5"
            />
            <p class="text-sm text-red-300">{{ errorMessage }}</p>
          </div>
        </div>

        <form @submit.prevent="handleRegister" class="space-y-6">
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              Имя <span class="text-slate-500">(опционально)</span>
            </label>
            <input
              v-model="fullName"
              type="text"
              placeholder="Иван Иванов"
              class="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
            />
          </div>

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
              minlength="8"
              placeholder="Минимум 8 символов"
              class="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              :class="{ 'border-red-500': passwordError }"
            />
            <p v-if="passwordError" class="text-red-500 text-xs mt-1">
              {{ passwordError }}
            </p>
            <p v-else class="text-slate-500 text-xs mt-1">
              Минимум 8 символов, должен содержать заглавную букву, строчную
              букву и цифру
            </p>
          </div>

          <!-- Confirm Password -->
          <div>
            <label class="block text-sm font-medium text-slate-300 mb-2">
              Подтвердите пароль
            </label>
            <input
              v-model="confirmPassword"
              type="password"
              required
              placeholder="Повторите пароль"
              class="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              :class="{ 'border-red-500': confirmPasswordError }"
            />
            <p v-if="confirmPasswordError" class="text-red-500 text-xs mt-1">
              {{ confirmPasswordError }}
            </p>
          </div>

          <button
            type="submit"
            :disabled="isLoading || !isFormValid"
            class="w-full px-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition flex items-center justify-center gap-2"
          >
            <RefreshCwIcon v-if="isLoading" class="w-5 h-5 animate-spin" />
            <span>{{
              isLoading ? "Регистрация..." : "Зарегистрироваться"
            }}</span>
          </button>
        </form>

        <div class="mt-6 text-center">
          <p class="text-sm text-slate-400">
            Уже есть аккаунт?
            <router-link
              to="/login"
              class="text-emerald-500 hover:text-emerald-400 font-semibold"
            >
              Войти
            </router-link>
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { register } from "../services/auth.js";
import {
  AlertOctagonIcon,
  RefreshCwIcon,
  TrendingUpIcon,
} from "lucide-vue-next";

const router = useRouter();

const fullName = ref("");
const email = ref("");
const password = ref("");
const confirmPassword = ref("");
const isLoading = ref(false);
const errorMessage = ref("");
const passwordError = ref("");
const confirmPasswordError = ref("");

const validatePassword = () => {
  const pwd = password.value;

  if (pwd.length < 8) {
    passwordError.value = "Минимум 8 символов";
    return false;
  }

  if (!/[A-Z]/.test(pwd)) {
    passwordError.value = "Должна быть хотя бы одна заглавная буква";
    return false;
  }

  if (!/[a-z]/.test(pwd)) {
    passwordError.value = "Должна быть хотя бы одна строчная буква";
    return false;
  }

  if (!/[0-9]/.test(pwd)) {
    passwordError.value = "Должна быть хотя бы одна цифра";
    return false;
  }

  passwordError.value = "";
  return true;
};

const validateConfirmPassword = () => {
  if (confirmPassword.value && password.value !== confirmPassword.value) {
    confirmPasswordError.value = "Пароли не совпадают";
    return false;
  }
  confirmPasswordError.value = "";
  return true;
};

watch(password, () => {
  validatePassword();
  if (confirmPassword.value) {
    validateConfirmPassword();
  }
});

watch(confirmPassword, validateConfirmPassword);

const isFormValid = computed(() => {
  return (
    email.value &&
    password.value &&
    confirmPassword.value &&
    password.value === confirmPassword.value &&
    !passwordError.value &&
    !confirmPasswordError.value
  );
});

const handleRegister = async () => {
  if (!validatePassword() || !validateConfirmPassword()) {
    return;
  }

  isLoading.value = true;
  errorMessage.value = "";

  try {
    await register(email.value, password.value, fullName.value || null);

    router.push("/dashboard");
  } catch (error) {
    errorMessage.value = error.message;
  } finally {
    isLoading.value = false;
  }
};
</script>
