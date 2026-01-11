import axios from 'axios'
import {getAccessToken} from "../stores/authStore.js"

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8070'

const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
})

apiClient.interceptors.request.use((config) => {
    const token = getAccessToken()
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config

        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true

            try {
                const { getRefreshToken, saveTokens, clearTokens } = await import('../stores/authStore.js')
                const refreshToken = getRefreshToken()
                
                if (!refreshToken) {
                    clearTokens()
                    window.location.href = '/login'
                    return Promise.reject(error)
                }

                const response = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh/`, {
                    refresh_token: refreshToken
                })
                const { access_token, refresh_token } = response.data
                saveTokens(access_token, refresh_token || refreshToken)

                originalRequest.headers.Authorization = `Bearer ${access_token}`
                return apiClient(originalRequest)
            } catch (refreshError) {
                const { clearTokens } = await import('../stores/authStore.js')
                clearTokens()
                window.location.href = '/login'
                return Promise.reject(refreshError)
            }
        }
        return Promise.reject(error)
    }
)

const toSnakeCase = (str) => {
    return str.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`)
}

const toCamelCase = (str) => {
    return str.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
}

const convertKeysToSnakeCase = (obj) => {
    if (Array.isArray(obj)) {
        return obj.map(item => convertKeysToSnakeCase(item))
    }

    if (obj !== null && typeof obj === 'object') {
        return Object.keys(obj).reduce((acc, key) => {
            const snakeKey = toSnakeCase(key)
            acc[snakeKey] = convertKeysToSnakeCase(obj[key])
            return acc
        }, {})
    }

    return obj
}

const convertKeysToCamelCase = (obj) => {
    if (Array.isArray(obj)) {
        return obj.map(item => convertKeysToCamelCase(item))
    }

    if (obj !== null && typeof obj === 'object') {
        return Object.keys(obj).reduce((acc, key) => {
            const camelKey = toCamelCase(key)
            acc[camelKey] = convertKeysToCamelCase(obj[key])
            return acc
        }, {})
    }

    return obj
}

const transformConfigForBackend = (config) => {
    return {
        binance_api_key: config.apiKey,
        binance_api_secret: config.apiSecret,
        symbol: config.market,
        total_budget: config.budget,
        grid_length_pct: config.gridLength,
        first_order_offset_pct: config.firstOrderOffset,
        safety_orders_count: config.safetyOrdersCount,
        volume_scale_pct: config.scaleStepVolume,
        grid_shift_threshold_pct: config.priceStep,
        take_profit_pct: config.takeProfit,
        trailing_enabled: config.trailingEnabled || false,
        trailing_callback_pct: config.trailingCallbackPct || 0.8,
        trailing_min_profit_pct: config.trailingMinProfitPct || 1.0,
    }
}

export const transformConfigFromBackend = (backendConfig) => {
    return {
        apiKey: backendConfig.binanceApiKey || '',
        apiSecret: backendConfig.binanceApiSecret || '',
        market: backendConfig.symbol || 'ETH/USDT',
        budget: backendConfig.totalBudget || 1000,
        gridLength: backendConfig.gridLengthPct || 5.0,
        firstOrderOffset: backendConfig.firstOrderOffsetPct || 0.05,
        safetyOrdersCount: backendConfig.safetyOrdersCount || 5,
        scaleStepVolume: backendConfig.volumeScalePct || 0,
        priceStep: backendConfig.gridShiftThresholdPct || 2.0,
        takeProfit: backendConfig.takeProfitPct || 2.0,
        trailingEnabled: backendConfig.trailingEnabled || false,
        trailingCallbackPct: backendConfig.trailingCallbackPct || 0.8,
        trailingMinProfitPct: backendConfig.trailingMinProfitPct || 1.0,
    }
}

export const setupBotConfig = async (config) => {
    try {
        const payload = transformConfigForBackend(config)
        const response = await apiClient.post('/api/v1/bot_config/setup/', payload)
        return convertKeysToCamelCase(response.data)
    } catch (error) {
        handleApiError(error)
    }
}

export const startBot = async (configId) => {
    try {
        const response = await apiClient.post(`/api/v1/bot_config/${configId}/start/`)
        return convertKeysToCamelCase(response.data)
    } catch (error) {
        handleApiError(error)
    }
}

export const getBotConfig = async (configId) => {
    try {
        const response = await apiClient.get(`/api/v1/bot_config/${configId}/`)
        return convertKeysToCamelCase(response.data)
    } catch (error) {
        handleApiError(error)
    }
}

export const listBotConfigs = async () => {
    try {
        const response = await apiClient.get('/api/v1/bot_config/')
        return response.data.map(c => convertKeysToCamelCase(c))
    } catch (error) {
        handleApiError(error)
    }
}

export const getLastActiveConfig = async () => {
    try {
        const response = await apiClient.get('/api/v1/bot_config/last-active/')
        return response.data ? convertKeysToCamelCase(response.data) : null
    } catch (error) {
        handleApiError(error)
    }
}

export const getCycle = async (cycleId) => {
    try {
        const response = await apiClient.get(`/api/v1/cycles/${cycleId}`)
        return convertKeysToCamelCase(response.data)
    } catch (error) {
        handleApiError(error)
    }
}

export const getStats = async (configId) => {
    try {
        const response = await apiClient.get(`/api/v1/stats/`, {
            params: {config_id: configId}
        })
        return convertKeysToCamelCase(response.data)
    } catch (error) {
        handleApiError(error)
    }
}

export const stopBot = async (configId) => {
    try {
        const response = await apiClient.post(`/api/v1/bot_config/${configId}/stop/`)
        return convertKeysToCamelCase(response.data)
    } catch (error) {
        handleApiError(error)
    }
}

export const checkBalance = async (apiKey, apiSecret) => {
    try {
        const response = await apiClient.post('/api/v1/user/balance/', {
            api_key: apiKey,
            api_secret: apiSecret
        })
        return convertKeysToCamelCase(response.data)
    } catch (error) {
        handleApiError(error)
    }
}

export const getTrailingStats = async (configId) => {
    try {
        const response = await apiClient.get(`/api/v1/bot_config/${configId}/trailing-stats/`)
        return convertKeysToCamelCase(response.data)
    } catch (error) {
        handleApiError(error)
    }
}

const handleApiError = (error) => {
    if (error.response) {
        const errorMessage = error.response.data?.detail || error.response.statusText
        throw new Error(`API Error (${error.response.status}): ${errorMessage}`)
    } else if (error.request) {
        throw new Error('Network Error: Unable to reach the server. Check if backend is running.')
    } else {
        throw new Error(`Error: ${error.message}`)
    }
}

export default {
    setupBotConfig,
    startBot,
    getBotConfig,
    listBotConfigs,
    getLastActiveConfig,
    getCycle,
    stopBot,
    checkBalance,
    getStats,
    getTrailingStats,
}
