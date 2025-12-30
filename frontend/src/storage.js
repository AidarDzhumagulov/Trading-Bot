const STORAGE_KEY = 'dca_bot_config_id'

export function loadConfigId() {
    const configId = localStorage.getItem(STORAGE_KEY)
    return configId || null
}

export function saveConfigId(configId) {
    if (configId) {
        localStorage.setItem(STORAGE_KEY, configId)
    } else {
        localStorage.removeItem(STORAGE_KEY)
    }
}

export function clearConfigId() {
    localStorage.removeItem(STORAGE_KEY)
}