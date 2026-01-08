import axios from "axios";
import {clearTokens, getAccessToken, getRefreshToken, saveTokens} from "../stores/authStore.js";

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8070'

const authClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'ContentType': 'application/json',
    },
})

authClient.interceptors.request.use((config) => {
    const access_token = getAccessToken()
    if (access_token) {
        config.headers.Authorization = `Bearer ${access_token}`
    }
    return config
})


authClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config

        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true

            try {
                const refreshToken = getRefreshToken()
                if (!refreshToken) {
                    clearTokens()
                    window.location.href = '/login'
                    return Promise.reject(error)
                }
                const response = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh/`, {
                    refresh_token: refreshToken
                })

                const {access_token, refresh_token} = response.data
                saveTokens(access_token, refresh_token || refreshToken)

                originalRequest.headers.Authorization = `Bearer ${access_token}`
                return authClient(originalRequest)
            } catch (refreshError) {
                clearTokens()
                window.location.href = '/login'
                return Promise.reject(refreshError)
            }
        }
        return Promise.reject(error)
    }
)


export const register = async (email, password, fullName = null) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/api/v1/auth/register/`, {
            email,
            password,
            fullName: fullName,
        })

        const {access_token, refresh_token} = response.data
        saveTokens(access_token, refresh_token)

        return response.data
    } catch (error) {
        throw handleAuthError(error)
    }
}


export const login = async (email, password) => {
    try {
        const response = await axios.post(`${API_BASE_URL}/api/v1/auth/login/`, {
            email,
            password,
        })
        const {access_token, refresh_token} = response.data
        saveTokens(access_token, refresh_token)

        return response.data
    } catch (error) {
        throw handleAuthError(error)
    }
}


export const logout = async () => {
    try {
        const refreshToken = getRefreshToken()
        if (refreshToken) {
            await authClient.post('/api/v1/auth/logout/', {
                refresh_token: refreshToken
            })
        }
    } catch (error) {
        console.error('Logout error:', error)
    } finally {
        clearTokens()
    }
}


// export const getCurrentUser = async () => {
//     try {
//         const response = await authClient.get('/api/v1/auth/me')
//         return response.data
//     } catch (error) {
//         throw handleAuthError(error)
//     }
// }

const handleAuthError = (error) => {
    if (error.response) {
        const message = error.response.data?.detail || error.response.statusText
        return new Error(message)
    } else if (error.request) {
        return new Error('Network Error: Unable to reach the server')
    } else {
        return new Error(error.message)
    }
}

export default {
    register,
    login,
    logout,
    authClient,
    // getCurrentUser,
}