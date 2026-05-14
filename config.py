import os

try:
    import streamlit as st
except Exception:
    st = None


def _get_secret(section, key, default=""):
    if st is None:
        return default
    try:
        return st.secrets.get(section, {}).get(key, default)
    except Exception:
        return default


def _get_config(env_name, section, key, default=""):
    return os.getenv(env_name) or _get_secret(section, key, default)



DB_NAME = "Smart_Agriculture.db"

SYNC_INTERVAL = 300  # 秒
DEBUG_MODE = True

USERNAME = _get_config("IOT_USERNAME", "iot", "username")
PASSWORD = _get_config("IOT_PASSWORD", "iot", "password")
API_KEY = _get_config("IOT_API_KEY", "iot", "api_key")

WEATHER_API_KEY = _get_config("WEATHER_API_KEY", "weather", "api_key")
DINGTALK_OFFICIAL_WEBHOOK = _get_config("DINGTALK_OFFICIAL_WEBHOOK", "dingtalk", "official_webhook")


METRIC_BEHAVIOR = {
    "空温": {"unit": "℃", "min": -10, "max": 60, "step": 0.5, "def_min": 10.0, "def_max": 35.0},
    "空湿": {"unit": "%", "min": 0, "max": 100, "step": 1.0, "def_min": 40.0, "def_max": 90.0},
    "土壤温度": {"unit": "℃", "min": -5, "max": 50, "step": 0.5, "def_min": 15.0, "def_max": 30.0},
    "ph": {"unit": "ph", "min": 0.0, "max": 14.0, "step": 0.1, "def_min": 5.5, "def_max": 7.5},
    "ec": {"unit": "us/cm", "min": 0, "max": 10000, "step": 10.0, "def_min": 500.0, "def_max": 3000.0},
    "光强": {"unit": "Lux", "min": 0, "max": 150000, "step": 100.0, "def_min": 1000.0, "def_max": 100000.0},
    "CO2": {"unit": "ppm", "min": 0, "max": 5000, "step": 10.0, "def_min": 400.0, "def_max": 1500.0},
}
