DB_NAME = "Smart_Agriculture.db"

SYNC_INTERVAL = 300  # 秒

USERNAME = "yys-zhw"
PASSWORD = "123456"
API_KEY = "ffec4dee9fa344208f9c3b6c870b4879"

WEATHER_API_KEY = "d8bd7e4c3d59315deb2cbb5931296891"

DEBUG_MODE = True

METRIC_BEHAVIOR = {
    "空温": {"unit": "℃", "min": -10, "max": 60, "step": 0.5, "def_min": 10.0, "def_max": 35.0},
    "空湿": {"unit": "%", "min": 0, "max": 100, "step": 1.0, "def_min": 40.0, "def_max": 90.0},
    "土壤温度": {"unit": "℃", "min": -5, "max": 50, "step": 0.5, "def_min": 15.0, "def_max": 30.0},
    "ph": {"unit": "ph", "min": 0.0, "max": 14.0, "step": 0.1, "def_min": 5.5, "def_max": 7.5},
    "ec": {"unit": "us/cm", "min": 0, "max": 10000, "step": 10.0, "def_min": 500.0, "def_max": 3000.0},
    "光强": {"unit": "Lux", "min": 0, "max": 150000, "step": 100.0, "def_min": 1000.0, "def_max": 100000.0},
    "CO2": {"unit": "ppm", "min": 0, "max": 5000, "step": 10.0, "def_min": 400.0, "def_max": 1500.0},
}
