const STORAGE_KEY_ACCESS_TOKEN = "access_token"
const STORAGE_KEY_REFRESH_TOKEN = 'refresh_token'
const STORAGE_KEY_USER = 'user'


export function saveTokens(accessToken, refreshToken) {
    localStorage.setItem(STORAGE_KEY_ACCESS_TOKEN, accessToken)
    localStorage.setItem(STORAGE_KEY_REFRESH_TOKEN, refreshToken)
}

export function getAccessToken() {
    return localStorage.getItem(STORAGE_KEY_ACCESS_TOKEN)
}

export function getRefreshToken() {
    return localStorage.getItem(STORAGE_KEY_REFRESH_TOKEN)
}

export function clearTokens() {
    localStorage.removeItem(STORAGE_KEY_ACCESS_TOKEN)
    localStorage.removeItem(STORAGE_KEY_REFRESH_TOKEN)
    localStorage.removeItem(STORAGE_KEY_USER)
}

export function saveUser(user) {
    localStorage.setItem(STORAGE_KEY_USER, JSON.stringify(user))
}

export function getUser() {
    const userStr = localStorage.getItem(STORAGE_KEY_USER)

    if (userStr) {
        try {
            return JSON.parse(userStr)
        } catch (e) {
            return null
        }
    }
    return null
}

export function isAuthenticated() {
    return !!getAccessToken()
}
