const STORAGE_KEY_CONFIG_ID = "dca_bot_config_id";
const STORAGE_KEY_CONFIG = "dca_bot_config";

export function loadConfigId() {
  const configId = localStorage.getItem(STORAGE_KEY_CONFIG_ID);
  return configId || null;
}

export function saveConfigId(configId) {
  if (configId) {
    localStorage.setItem(STORAGE_KEY_CONFIG_ID, configId);
  } else {
    localStorage.removeItem(STORAGE_KEY_CONFIG_ID);
  }
}

export function clearConfigId() {
  localStorage.removeItem(STORAGE_KEY_CONFIG_ID);
}

export function clearAllConfigData() {
  localStorage.removeItem(STORAGE_KEY_CONFIG_ID);
  localStorage.removeItem(STORAGE_KEY_CONFIG);
}

export function loadConfig() {
  const configStr = localStorage.getItem(STORAGE_KEY_CONFIG);
  if (configStr) {
    try {
      return JSON.parse(configStr);
    } catch (e) {
      return null;
    }
  }
  return null;
}

export function saveConfig(config) {
  if (config) {
    localStorage.setItem(STORAGE_KEY_CONFIG, JSON.stringify(config));
  } else {
    localStorage.removeItem(STORAGE_KEY_CONFIG);
  }
}
