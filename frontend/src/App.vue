<template>
  <div class="min-h-screen bg-slate-950 p-4 md:p-6 lg:p-8">
    <header class="mb-8">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-3xl font-bold text-slate-100 flex items-center gap-3">
            <TrendingUpIcon class="w-8 h-8 text-emerald-500"/>
            DCA Binance Bot
          </h1>
          <p class="text-slate-400 mt-1">Облачный терминал для торговли по стратегии DCA</p>
        </div>
        <div class="flex items-center gap-2">
          <div class="h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></div>
          <span class="text-sm text-slate-400">Онлайн</span>
        </div>
      </div>
    </header>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">

      <div class="space-y-6">

        <div class="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-xl">
          <div class="flex items-center gap-2 mb-4">
            <KeyIcon class="w-5 h-5 text-slate-400"/>
            <h2 class="text-xl font-semibold text-slate-100">API Учетные данные</h2>
          </div>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Binance API Key
                <span class="text-slate-500 text-xs ml-1">(Обязательно для торговли)</span>
              </label>
              <input
                  v-model="config.apiKey"
                  @blur="validateBalance"
                  type="text"
                  placeholder="Введите ваш Binance API Key"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              />
            </div>
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Binance API Secret
                <span class="text-slate-500 text-xs ml-1">(Храните в безопасности)</span>
              </label>
              <input
                  v-model="config.apiSecret"
                  @blur="validateBalance"
                  type="password"
                  placeholder="Введите ваш Binance API Secret"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              />
            </div>
          </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-xl">
          <div class="flex items-center gap-2 mb-4">
            <SettingsIcon class="w-5 h-5 text-slate-400"/>
            <h2 class="text-xl font-semibold text-slate-100">Настройки торговли</h2>
          </div>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Торговая пара
                <span class="text-slate-500 text-xs ml-1">(Выберите рынок)</span>
              </label>
              <select
                  v-model="config.market"
                  @change="updateMockPrice"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition cursor-pointer"
              >
                <option value="BTC/USDT">BTC/USDT</option>
                <option value="ETH/USDT">ETH/USDT</option>
              </select>
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Бюджет (USDT)
                <span v-if="balance.freeUsdt > 0" class="text-slate-500 text-xs ml-1">
                  (Доступно: {{ balance.freeUsdt.toFixed(2) }} USDT)
                </span>
                <span v-else-if="isCheckingBalance" class="text-slate-500 text-xs ml-1">
                  Проверка баланса...
                </span>
                <span v-else class="text-slate-500 text-xs ml-1">
                  (Введите API ключи для проверки баланса)
                </span>
              </label>
              <input
                  v-model.number="config.budget"
                  @input="validateBalance"
                  type="number"
                  min="10"
                  :max="balance.freeUsdt || 999999"
                  placeholder="Введите бюджет в USDT (мин: 10)"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                  :class="{ 'border-red-500': balanceError || (config.budget > balance.freeUsdt && balance.freeUsdt > 0) }"
              />
              <p v-if="balanceError" class="text-red-500 text-xs mt-1">
                {{ balanceError }}
              </p>
              <p v-else-if="config.budget > balance.freeUsdt && balance.freeUsdt > 0" class="text-red-500 text-xs mt-1">
                Бюджет превышает доступный баланс!
              </p>
              <p v-else-if="config.budget < 10" class="text-red-500 text-xs mt-1">
                Минимальный бюджет: 10 USDT
              </p>
            </div>
          </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-xl">
          <div class="flex items-center gap-2 mb-4">
            <GridIcon class="w-5 h-5 text-slate-400"/>
            <h2 class="text-xl font-semibold text-slate-100">Настройка сетки</h2>
          </div>
          <div class="space-y-4">
            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Длина сетки (%)
                <span class="text-slate-500 text-xs ml-1">(Диапазон цен для размещения ордеров)</span>
              </label>
              <input
                  v-model.number="config.gridLength"
                  type="number"
                  min="0"
                  step="0.1"
                  placeholder="например, 5.0"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                  :class="{ 'border-red-500': config.gridLength < 0 }"
              />
              <p v-if="config.gridLength < 0" class="text-red-500 text-xs mt-1">
                Длина сетки не может быть отрицательной!
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Отступ первого ордера (%)
                <span class="text-slate-500 text-xs ml-1">(Расстояние от текущей цены)</span>
              </label>
              <input
                  v-model.number="config.firstOrderOffset"
                  type="number"
                  min="0"
                  step="0.1"
                  placeholder="например, 0.05"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Количество страховочных ордеров
                <span class="text-slate-500 text-xs ml-1">(Ордера на покупку для усреднения)</span>
              </label>
              <input
                  v-model.number="config.safetyOrdersCount"
                  type="number"
                  min="1"
                  max="20"
                  placeholder="например, 5"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Масштабирование объема (%)
                <span class="text-slate-500 text-xs ml-1">(Процент увеличения объема каждого следующего ордера)</span>
              </label>
              <input
                  v-model.number="config.scaleStepVolume"
                  type="number"
                  min="0"
                  step="10"
                  placeholder="например, 50"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              />
              <p class="text-slate-500 text-xs mt-1">
                0% = тот же объем, 50% = увеличение в 1.5 раза, 100% = увеличение в 2 раза
              </p>
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Шаг цены (%)
                <span class="text-slate-500 text-xs ml-1">(Процент сдвига сетки)</span>
              </label>
              <input
                  v-model.number="config.priceStep"
                  type="number"
                  min="0.1"
                  step="0.1"
                  placeholder="например, 2.0"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <label class="block text-sm font-medium text-slate-300 mb-2">
                Тейк-профит (%)
                <span class="text-slate-500 text-xs ml-1">(Целевая прибыль за цикл)</span>
              </label>
              <input
                  v-model.number="config.takeProfit"
                  type="number"
                  min="0.1"
                  step="0.1"
                  placeholder="например, 2.0"
                  class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
              />
            </div>
          </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-xl">
          <div class="flex items-center gap-2 mb-4">
            <TrendingUpIcon class="w-5 h-5 text-slate-400"/>
            <h2 class="text-xl font-semibold text-slate-100">Trailing Take Profit</h2>
          </div>
          <div class="space-y-4">
            <div class="flex items-center gap-3">
              <input
                  v-model="config.trailingEnabled"
                  type="checkbox"
                  id="trailingEnabled"
                  class="w-5 h-5 rounded bg-slate-800 border-slate-700 text-emerald-600 focus:ring-emerald-500 focus:ring-2"
              />
              <label for="trailingEnabled" class="text-sm font-medium text-slate-300 cursor-pointer">
                Включить Trailing Take Profit
              </label>
            </div>
            <p class="text-xs text-slate-500">
              Автоматически отслеживает максимальную цену и продает при откате, максимизируя прибыль
            </p>

            <div v-if="config.trailingEnabled" class="space-y-4 pt-2 border-t border-slate-700">
              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">
                  Процент отката от максимума (%)
                  <span class="text-slate-500 text-xs ml-1">(Callback для продажи)</span>
                </label>
                <input
                    v-model.number="config.trailingCallbackPct"
                    type="number"
                    min="0"
                    max="5"
                    step="0.1"
                    placeholder="например, 0.8"
                    class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                />
                <p class="text-slate-500 text-xs mt-1">
                  Рекомендуется: 0.5-1.2%. Автоматически адаптируется к волатильности
                </p>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-300 mb-2">
                  Минимальная гарантированная прибыль (%)
                  <span class="text-slate-500 text-xs ml-1">(Защита от убытков)</span>
                </label>
                <input
                    v-model.number="config.trailingMinProfitPct"
                    type="number"
                    min="0"
                    max="10"
                    step="0.1"
                    placeholder="например, 1.0"
                    class="w-full px-4 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition"
                />
                <p class="text-slate-500 text-xs mt-1">
                  Если цена падает ниже этого уровня - аварийная продажа по рынку
                </p>
              </div>
            </div>
          </div>
        </div>

        <div class="flex gap-4">
          <button
              @click="startBot"
              :disabled="!isConfigValid || botStatus === 'active' || isLoading"
              class="flex-1 px-6 py-3 bg-emerald-600 hover:bg-emerald-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition flex items-center justify-center gap-2 shadow-lg hover:shadow-emerald-500/50"
          >
            <RefreshCwIcon v-if="isLoading" class="w-5 h-5 animate-spin"/>
            <PlayIcon v-else class="w-5 h-5"/>
            {{ isLoading ? 'Запуск...' : botStatus === 'active' ? 'Бот работает...' : 'Запустить бота' }}
          </button>
          <button
              @click="emergencyStop"
              :disabled="botStatus !== 'active' || isLoading"
              class="flex-1 px-6 py-3 bg-red-600 hover:bg-red-700 disabled:bg-slate-700 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition flex items-center justify-center gap-2 shadow-lg hover:shadow-red-500/50"
          >
            <RefreshCwIcon v-if="isLoading" class="w-5 h-5 animate-spin"/>
            <AlertOctagonIcon v-else class="w-5 h-5"/>
            {{ isLoading ? 'Остановка...' : 'Экстренная остановка' }}
          </button>
        </div>

        <div v-if="errorMessage" class="mt-4 p-4 bg-red-900/30 border border-red-800 rounded-lg">
          <div class="flex items-start gap-3">
            <AlertOctagonIcon class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5"/>
            <div class="flex-1">
              <p class="text-sm font-semibold text-red-400 mb-1">Ошибка</p>
              <p class="text-sm text-red-300">{{ errorMessage }}</p>
            </div>
            <button @click="errorMessage = ''" class="text-red-400 hover:text-red-300">
              <span class="text-xl leading-none">&times;</span>
            </button>
          </div>
        </div>

        <div v-if="botStatus === 'active' && configId"
             class="mt-4 p-4 bg-emerald-900/30 border border-emerald-800 rounded-lg">
          <div class="flex items-start gap-3">
            <ActivityIcon class="w-5 h-5 text-emerald-500 flex-shrink-0 mt-0.5"/>
            <div class="flex-1">
              <p class="text-sm font-semibold text-emerald-400 mb-1">Бот активен</p>
              <p class="text-xs text-emerald-300">ID конфигурации: {{ configId }}</p>
              <p v-if="cycleId" class="text-xs text-emerald-300">ID цикла: {{ cycleId }}</p>
            </div>
          </div>
        </div>
      </div>

      <div class="space-y-6">

        <div class="grid grid-cols-2 gap-4">
          <div
              class="bg-gradient-to-br from-emerald-900/30 to-slate-900 border border-emerald-800/50 rounded-lg p-6 shadow-xl">
            <div class="flex items-center gap-2 mb-2">
              <DollarSignIcon class="w-5 h-5 text-emerald-500"/>
              <h3 class="text-sm font-medium text-slate-400">Общая прибыль</h3>
            </div>
            <p class="text-3xl font-bold text-emerald-500">
              {{ formatCurrency(dashboard.totalProfit) }}
            </p>
            <p class="text-xs text-slate-500 mt-1">USDT</p>
            <p v-if="dashboard.roiPct !== 0" class="text-xs mt-1"
               :class="dashboard.roiPct >= 0 ? 'text-emerald-400' : 'text-red-400'">
              ROI: {{ dashboard.roiPct >= 0 ? '+' : '' }}{{ dashboard.roiPct.toFixed(2) }}%
            </p>
          </div>

          <div
              class="bg-gradient-to-br from-blue-900/30 to-slate-900 border border-blue-800/50 rounded-lg p-6 shadow-xl">
            <div class="flex items-center gap-2 mb-2">
              <RefreshCwIcon class="w-5 h-5 text-blue-500"/>
              <h3 class="text-sm font-medium text-slate-400">Завершенные циклы</h3>
            </div>
            <p class="text-3xl font-bold text-blue-500">
              {{ dashboard.completedCycles }}
            </p>
            <p class="text-xs text-slate-500 mt-1">Всего циклов</p>
            <p v-if="dashboard.winRate > 0" class="text-xs mt-1 text-blue-400">
              Win Rate: {{ dashboard.winRate.toFixed(1) }}%
            </p>
          </div>
        </div>

        <div v-if="dashboard.completedCycles > 0" class="grid grid-cols-4 gap-4">
          <div class="bg-slate-800/50 rounded-lg p-4">
            <p class="text-xs text-slate-500 mb-1">Средняя прибыль</p>
            <p class="text-lg font-semibold text-slate-100">
              ${{ formatNumber(dashboard.avgProfitPerCycle) }}
            </p>
          </div>
          <div class="bg-slate-800/50 rounded-lg p-4">
            <p class="text-xs text-slate-500 mb-1">Средняя длительность</p>
            <p class="text-lg font-semibold text-slate-100">
              {{ dashboard.avgCycleDurationHours.toFixed(1) }}ч
            </p>
          </div>
          <div class="bg-slate-800/50 rounded-lg p-4">
            <p class="text-xs text-slate-500 mb-1">Лучший цикл</p>
            <p class="text-lg font-semibold text-emerald-500">
              ${{ formatNumber(dashboard.bestCycleProfit) }}
            </p>
          </div>
          <div class="bg-slate-800/50 rounded-lg p-4">
            <p class="text-xs text-slate-500 mb-1">Худший цикл</p>
            <p class="text-lg font-semibold text-red-500">
              ${{ formatNumber(dashboard.worstCycleProfit) }}
            </p>
          </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-xl">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-2">
              <ActivityIcon class="w-5 h-5 text-slate-400"/>
              <h2 class="text-xl font-semibold text-slate-100">Текущий цикл</h2>
            </div>
            <span
                class="px-3 py-1 rounded-full text-xs font-semibold"
                :class="botStatus === 'active' ? 'bg-emerald-900/50 text-emerald-500 border border-emerald-700' : 'bg-slate-800 text-slate-400 border border-slate-700'"
            >
              {{ botStatus === 'active' ? 'Активен' : 'Ожидание' }}
            </span>
          </div>

          <div class="mb-6">
            <div class="flex justify-between text-sm mb-2">
              <span class="text-slate-400">Исполнено страховочных ордеров</span>
              <span class="text-slate-300 font-semibold">
                {{ dashboard.currentCycle.filledOrders }} / {{ config.safetyOrdersCount }}
              </span>
            </div>
            <div class="w-full bg-slate-800 rounded-full h-3 overflow-hidden">
              <div
                  class="bg-gradient-to-r from-emerald-600 to-emerald-500 h-3 rounded-full transition-all duration-500"
                  :style="{ width: `${safetyOrderProgress}%` }"
              ></div>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div class="bg-slate-800/50 rounded-lg p-4">
              <p class="text-xs text-slate-500 mb-1">Текущая средняя цена</p>
              <p class="text-lg font-semibold text-slate-100">
                ${{ formatNumber(dashboard.currentCycle.averagePrice) }}
              </p>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-4">
              <p class="text-xs text-slate-500 mb-1">Цена тейк-профита</p>
              <p class="text-lg font-semibold text-emerald-500">
                ${{ formatNumber(dashboard.currentCycle.takeProfitPrice) }}
              </p>
              <p v-if="dashboard.currentCycle.effectiveTpPct > 0" class="text-xs text-emerald-400 mt-1">
                Эффективный TP: {{ dashboard.currentCycle.effectiveTpPct.toFixed(2) }}%
              </p>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-4">
              <p class="text-xs text-slate-500 mb-1">Общий объем</p>
              <p class="text-lg font-semibold text-slate-100">
                {{ formatNumber(dashboard.currentCycle.totalVolume) }}
              </p>
              <p class="text-xs text-slate-500">{{ config.market.split('/')[0] }}</p>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-4">
              <p class="text-xs text-slate-500 mb-1">Инвестированный капитал</p>
              <p class="text-lg font-semibold text-slate-100">
                ${{ formatNumber(dashboard.currentCycle.investedCapital) }}
              </p>
            </div>
          </div>

          <div v-if="dashboard.currentCycle.unrealizedProfit !== 0 || dashboard.currentCycle.expectedProfit !== 0" class="grid grid-cols-2 gap-4 mt-4">
            <div class="bg-slate-800/50 rounded-lg p-4">
              <p class="text-xs text-slate-500 mb-1">Текущая прибыль</p>
              <p class="text-lg font-semibold"
                 :class="dashboard.currentCycle.unrealizedProfit >= 0 ? 'text-emerald-500' : 'text-red-500'">
                {{ dashboard.currentCycle.unrealizedProfit >= 0 ? '+' : '' }}${{ formatNumber(dashboard.currentCycle.unrealizedProfit) }}
              </p>
            </div>
            <div class="bg-slate-800/50 rounded-lg p-4">
              <p class="text-xs text-slate-500 mb-1">Ожидаемая прибыль</p>
              <p class="text-lg font-semibold text-emerald-500">
                ${{ formatNumber(dashboard.currentCycle.expectedProfit) }}
              </p>
            </div>
          </div>

          <div v-if="dashboard.currentCycle.accumulatedDust > 0" class="mt-4 bg-slate-800/30 rounded-lg p-3">
            <p class="text-xs text-slate-400">
              Накопленная пыль: {{ dashboard.currentCycle.accumulatedDust.toFixed(8) }} {{ config.market.split('/')[0] }}
            </p>
          </div>
        </div>

        <div v-if="dashboard.trailingStats.trailingEnabled" class="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-xl">
          <div class="flex items-center gap-2 mb-4">
            <TrendingUpIcon class="w-5 h-5 text-slate-400"/>
            <h2 class="text-xl font-semibold text-slate-100">Trailing Take Profit</h2>
          </div>

          <div v-if="dashboard.trailingStats.config" class="mb-6">
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Callback %</p>
                <p class="text-lg font-semibold text-slate-100">
                  {{ dashboard.trailingStats.config.callbackPct }}%
                </p>
              </div>
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Min Profit %</p>
                <p class="text-lg font-semibold text-slate-100">
                  {{ dashboard.trailingStats.config.minProfitPct }}%
                </p>
              </div>
            </div>
          </div>

          <div v-if="dashboard.trailingStats.statistics" class="mb-6">
            <h3 class="text-sm font-semibold text-slate-300 mb-3">Статистика</h3>
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Всего циклов с trailing</p>
                <p class="text-lg font-semibold text-slate-100">
                  {{ dashboard.trailingStats.statistics.totalCyclesWithTrailing }}
                </p>
              </div>
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Закрытых циклов</p>
                <p class="text-lg font-semibold text-slate-100">
                  {{ dashboard.trailingStats.statistics.closedCycles }}
                </p>
              </div>
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Аварийных выходов</p>
                <p class="text-lg font-semibold text-red-500">
                  {{ dashboard.trailingStats.statistics.emergencyExits }}
                </p>
              </div>
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Success Rate</p>
                <p class="text-lg font-semibold text-emerald-500">
                  {{ (dashboard.trailingStats.statistics.successRatePct || 0).toFixed(1) }}%
                </p>
              </div>
              <div class="bg-slate-800/50 rounded-lg p-4 col-span-2">
                <p class="text-xs text-slate-500 mb-1">Среднее улучшение прибыли</p>
                <p class="text-lg font-semibold text-emerald-500">
                  +{{ dashboard.trailingStats.statistics.avgImprovementPct || 0 }}%
                </p>
              </div>
            </div>
          </div>

          <div v-if="dashboard.trailingStats.currentCycle" class="border-t border-slate-700 pt-4">
            <h3 class="text-sm font-semibold text-slate-300 mb-3">Текущий цикл</h3>
            <div class="grid grid-cols-2 gap-4">
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Цена активации</p>
                <p class="text-lg font-semibold text-slate-100">
                  ${{ formatNumber(dashboard.trailingStats.currentCycle.activationPrice || 0) }}
                </p>
              </div>
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Максимальная цена</p>
                <p class="text-lg font-semibold text-emerald-500">
                  ${{ formatNumber(dashboard.trailingStats.currentCycle.maxPriceTracked || 0) }}
                </p>
              </div>
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Текущий TP</p>
                <p class="text-lg font-semibold text-slate-100">
                  ${{ formatNumber(dashboard.trailingStats.currentCycle.currentTpPrice || 0) }}
                </p>
              </div>
              <div class="bg-slate-800/50 rounded-lg p-4">
                <p class="text-xs text-slate-500 mb-1">Потенциальная прибыль</p>
                <p class="text-lg font-semibold text-emerald-500">
                  {{ dashboard.trailingStats.currentCycle.potentialProfitPct ? dashboard.trailingStats.currentCycle.potentialProfitPct.toFixed(2) : '0.00' }}%
                </p>
              </div>
            </div>
          </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-xl">
          <div class="flex items-center gap-2 mb-4">
            <TrendingUpIcon class="w-5 h-5 text-slate-400"/>
            <h2 class="text-xl font-semibold text-slate-100">Текущая цена</h2>
          </div>
          <div class="flex items-end justify-between">
            <div>
              <p class="text-sm text-slate-400 mb-1">{{ config.market }}</p>
              <p class="text-4xl font-bold text-slate-100 flex items-center gap-2">
                ${{ formatNumber(dashboard.livePrice) }}
                <span
                    class="text-lg"
                    :class="priceChangeDirection === 'up' ? 'text-emerald-500' : priceChangeDirection === 'down' ? 'text-red-500' : 'text-slate-500'"
                >
                  {{ priceChangeDirection === 'up' ? '▲' : priceChangeDirection === 'down' ? '▼' : '━' }}
                </span>
              </p>
              <p class="text-sm text-slate-500 mt-1">Обновлено: {{ lastUpdateTime }}</p>
            </div>
            <div class="text-right">
              <p class="text-xs text-slate-500 mb-1">Изменение за 24ч</p>
              <p
                  class="text-xl font-semibold"
                  :class="dashboard.priceChange24h >= 0 ? 'text-emerald-500' : 'text-red-500'"
              >
                {{ dashboard.priceChange24h >= 0 ? '+' : '' }}{{ dashboard.priceChange24h.toFixed(2) }}%
              </p>
            </div>
          </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-lg p-6 shadow-xl">
          <div class="flex items-center gap-2 mb-4">
            <InfoIcon class="w-5 h-5 text-slate-400"/>
            <h2 class="text-xl font-semibold text-slate-100">Информация о стратегии DCA</h2>
          </div>
          <div class="space-y-3 text-sm">
            <div class="flex justify-between">
              <span class="text-slate-400">Размер базового ордера:</span>
              <span class="text-slate-100 font-semibold">${{ formatNumber(calculateBaseOrderSize()) }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-400">Диапазон сетки:</span>
              <span class="text-slate-100 font-semibold">
                ${{ formatNumber(calculateGridRange().min) }} - ${{ formatNumber(calculateGridRange().max) }}
              </span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-400">Ожидаемая максимальная просадка:</span>
              <span class="text-red-500 font-semibold">-{{ config.gridLength.toFixed(2) }}%</span>
            </div>
            <div class="flex justify-between">
              <span class="text-slate-400">Соотношение риск/прибыль:</span>
              <span class="text-slate-100 font-semibold">{{ calculateRiskRewardRatio() }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {computed, onMounted, onUnmounted, ref} from 'vue'
import {loadConfigId, saveConfigId, clearConfigId, loadConfig, saveConfig} from './storage.js'
import {
  ActivityIcon,
  AlertOctagonIcon,
  DollarSignIcon,
  GridIcon,
  InfoIcon,
  KeyIcon,
  PlayIcon,
  RefreshCwIcon,
  SettingsIcon,
  TrendingUpIcon
} from 'lucide-vue-next'
import {checkBalance, getStats, getTrailingStats, setupBotConfig, startBot as apiStartBot, stopBot as apiStopBot} from './services/api.js'

const config = ref({
  apiKey: '',
  apiSecret: '',
  market: 'ETH/USDT',
  budget: 1000,
  gridLength: 5.0,
  firstOrderOffset: 0.05,
  safetyOrdersCount: 5,
  scaleStepVolume: 0,
  priceStep: 2.0,
  takeProfit: 2.0,
  trailingEnabled: false,
  trailingCallbackPct: 0.8,
  trailingMinProfitPct: 1.0
})

const balance = ref({
  freeUsdt: 0,
  totalUsdt: 0
})
const balanceError = ref('')
const isCheckingBalance = ref(false)

const dashboard = ref({
  totalProfitUsdt: 0,
  totalProfit: 0,
  completedCycles: 0,
  livePrice: 0,
  priceChange24h: 0,
  currentMarketPrice: 0,
  totalInvested: 0,
  roiPct: 0,
  winRate: 0,
  avgProfitPerCycle: 0,
  avgCycleDurationHours: 0,
  bestCycleProfit: 0,
  worstCycleProfit: 0,
  currentUnrealizedProfit: 0,
  currentExpectedProfit: 0,
  trailingStats: {
    trailingEnabled: false,
    config: null,
    statistics: null,
    currentCycle: null,
    message: null
  },
  currentCycle: {
    averagePrice: 0,
    takeProfitPrice: 0,
    totalVolume: 0,
    investedCapital: 0,
    filledOrders: 0,
    filledOrdersCount: 0,
    tpOrderPrice: 0,
    tpOrderVolume: 0,
    totalQuoteSpent: 0,
    effectiveTpPct: 0,
    expectedProfit: 0,
    unrealizedProfit: 0,
    accumulatedDust: 0,
  }
})

const botStatus = ref('waiting')

const isLoading = ref(false)
const errorMessage = ref('')
const configId = ref(null)
const cycleId = ref(null)

const priceChangeDirection = ref('neutral')
const lastUpdateTime = ref(new Date().toLocaleTimeString())

let statsPollingInterval = null

const isConfigValid = computed(() => {
  const MIN_BUDGET = 10.0

  return (
      config.value.apiKey.trim() !== '' &&
      config.value.apiSecret.trim() !== '' &&
      config.value.budget >= MIN_BUDGET &&
      config.value.budget <= balance.value.freeUsdt &&
      balanceError.value === '' &&
      config.value.gridLength >= 0 &&
      config.value.safetyOrdersCount > 0 &&
      config.value.takeProfit > 0
  )
})

const safetyOrderProgress = computed(() => {
  const progress = (dashboard.value.currentCycle.filledOrders / config.value.safetyOrdersCount) * 100
  return Math.min(progress, 100)
})

const calculateBaseOrderSize = () => {
  if (config.value.budget <= 0) return 0

  const volumeMultiplier = config.value.scaleStepVolume / 100
  let totalVolumeUnits = 1

  for (let i = 1; i < config.value.safetyOrdersCount; i++) {
    totalVolumeUnits += Math.pow(volumeMultiplier, i)
  }

  return config.value.budget / totalVolumeUnits
}

const calculateGridRange = () => {
  const currentPrice = dashboard.value.livePrice
  const gridLengthDecimal = config.value.gridLength / 100
  const offsetDecimal = config.value.firstOrderOffset / 100

  const maxPrice = currentPrice * (1 - offsetDecimal)

  const minPrice = maxPrice * (1 - gridLengthDecimal)

  return {min: minPrice, max: maxPrice}
}

const calculateRiskRewardRatio = () => {
  if (config.value.gridLength === 0) return '0:0'
  const ratio = (config.value.takeProfit / config.value.gridLength).toFixed(2)
  return `1:${ratio}`
}

const formatCurrency = (value) => {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
}

const formatNumber = (value) => {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(value)
}

const validateBalance = async () => {
  if (!config.value.apiKey.trim() || !config.value.apiSecret.trim()) {
    balance.value = {freeUsdt: 0, totalUsdt: 0}
    balanceError.value = ''
    return
  }

  isCheckingBalance.value = true
  balanceError.value = ''

  try {
    const balanceData = await checkBalance(config.value.apiKey, config.value.apiSecret)
    balance.value = balanceData

    const MIN_BUDGET = 10.0

    if (balanceData.freeUsdt < MIN_BUDGET) {
      balanceError.value = `Недостаточно средств. Минимум ${MIN_BUDGET} USDT требуется. Доступно: ${balanceData.freeUsdt.toFixed(2)} USDT`
    } else if (config.value.budget > balanceData.freeUsdt) {
      balanceError.value = `Бюджет (${config.value.budget.toFixed(2)} USDT) превышает доступный баланс (${balanceData.freeUsdt.toFixed(2)} USDT)`
    }
  } catch (error) {
    balanceError.value = error.message
    balance.value = {freeUsdt: 0, totalUsdt: 0}
  } finally {
    isCheckingBalance.value = false
  }
}

const updateTrailingStats = async () => {
  if (!configId.value) return

  try {
    const trailing = await getTrailingStats(configId.value)
    dashboard.value.trailingStats = trailing || {
      trailingEnabled: false,
      config: null,
      statistics: null,
      currentCycle: null,
      message: null
    }
  } catch (error) {
    console.error('Failed to update trailing stats:', error)
    dashboard.value.trailingStats = {
      trailingEnabled: false,
      config: null,
      statistics: null,
      currentCycle: null,
      message: null
    }
  }
}

const updateStats = async () => {
  if (!configId.value) return

  try {
    const stats = await getStats(configId.value)
    console.log('Processed Stats:', stats)

    dashboard.value.totalProfit = stats.totalProfitUsdt || 0
    dashboard.value.completedCycles = stats.completedCycles || 0
    dashboard.value.totalInvested = stats.totalInvested || 0
    dashboard.value.roiPct = stats.roiPct || 0
    dashboard.value.winRate = stats.winRate || 0
    dashboard.value.avgProfitPerCycle = stats.avgProfitPerCycle || 0
    dashboard.value.avgCycleDurationHours = stats.avgCycleDurationHours || 0
    dashboard.value.bestCycleProfit = stats.bestCycleProfit || 0
    dashboard.value.worstCycleProfit = stats.worstCycleProfit || 0
    dashboard.value.currentUnrealizedProfit = stats.currentUnrealizedProfit || 0
    dashboard.value.currentExpectedProfit = stats.currentExpectedProfit || 0

    if (stats.currentCycle) {
      const cycle = stats.currentCycle
      dashboard.value.currentCycle.filledOrders = cycle.filledOrdersCount || 0
      dashboard.value.currentCycle.averagePrice = cycle.averagePrice || 0
      dashboard.value.currentCycle.takeProfitPrice = cycle.tpOrderPrice || 0
      dashboard.value.currentCycle.totalVolume = cycle.tpOrderVolume || 0
      dashboard.value.currentCycle.investedCapital = cycle.totalQuoteSpent || 0
      dashboard.value.currentCycle.effectiveTpPct = cycle.effectiveTpPct || 0
      dashboard.value.currentCycle.expectedProfit = cycle.expectedProfit || 0
      dashboard.value.currentCycle.unrealizedProfit = cycle.unrealizedProfit || 0
      dashboard.value.currentCycle.accumulatedDust = cycle.accumulatedDust || 0

      if (cycle.currentMarketPrice) {
        const oldPrice = dashboard.value.livePrice
        dashboard.value.livePrice = cycle.currentMarketPrice

        if (oldPrice > 0) {
          if (cycle.currentMarketPrice > oldPrice) {
            priceChangeDirection.value = 'up'
          } else if (cycle.currentMarketPrice < oldPrice) {
            priceChangeDirection.value = 'down'
          }
        }

        lastUpdateTime.value = new Date().toLocaleTimeString()
      }
    }

    await updateTrailingStats()
  } catch (error) {
    console.error('Failed to update stats:', error)
  }
}

const startStatsPolling = () => {
  if (statsPollingInterval) return

  updateStats()
  statsPollingInterval = setInterval(updateStats, 3000)
}

const stopStatsPolling = () => {
  if (statsPollingInterval) {
    clearInterval(statsPollingInterval)
    statsPollingInterval = null
  }
}

const startBot = async () => {
  if (!isConfigValid.value) {
    errorMessage.value = 'Пожалуйста, заполните все обязательные поля корректно!'
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    console.log('Creating bot configuration...')
    const setupResponse = await setupBotConfig(config.value)
    configId.value = setupResponse.id
    saveConfigId(configId.value)
    saveConfig(config.value)
    console.log('Config created:', setupResponse)

    console.log('Starting bot...')
    const startResponse = await apiStartBot(configId.value)
    cycleId.value = startResponse.cycleId
    console.log('Bot started:', startResponse)

    botStatus.value = 'active'

    startStatsPolling()

    console.log('Bot successfully started! Config ID:', configId.value, 'Cycle ID:', cycleId.value)
  } catch (error) {
    console.error('Failed to start bot:', error)
    errorMessage.value = error.message
    botStatus.value = 'waiting'
  } finally {
    isLoading.value = false
  }
}

const emergencyStop = async () => {
  if (!configId.value) {
    console.warn('No config ID available for stop')
    botStatus.value = 'waiting'
    resetCycle()
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    console.log('Stopping bot...')
    await apiStopBot(configId.value)
    console.log('Bot stopped successfully')

    botStatus.value = 'waiting'
    stopStatsPolling()
    resetCycle()

    configId.value = null
    cycleId.value = null
    clearConfigId()
  } catch (error) {
    console.error('Failed to stop bot:', error)
    errorMessage.value = error.message
  } finally {
    isLoading.value = false
  }
}

const resetCycle = () => {
  dashboard.value.currentCycle.filledOrders = 0
  dashboard.value.currentCycle.averagePrice = 0
  dashboard.value.currentCycle.takeProfitPrice = 0
  dashboard.value.currentCycle.totalVolume = 0
  dashboard.value.currentCycle.investedCapital = 0
}

onMounted(async () => {
  const savedConfigId = loadConfigId()
  const savedConfig = loadConfig()

  if (savedConfigId) {
    try {
      configId.value = savedConfigId

      if (savedConfig) {
        config.value = savedConfig
      }

      const stats = await getStats(savedConfigId)
      if (stats.currentCycle) {
        botStatus.value = 'active'
        startStatsPolling()
      } else {
        botStatus.value = 'waiting'
        await updateStats()
        await updateTrailingStats()
      }
    } catch (error) {
      console.warn('Failed to load saved config:', error)
      clearConfigId()
      configId.value = null
    }
  }
})

onUnmounted(() => {
  stopStatsPolling()
})
</script>

<style scoped>
.animate-pulse {
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
