import json
import requests
import re
import streamlit as st



def get_weather_amap(lat, lng, amap_key):
    """
    使用高德地图 API 获取实时天气
    """
    try:
        geo_url = "https://restapi.amap.com/v3/geocode/regeo"
        geo_params = {
            "location": f"{lng},{lat}", 
            "key": amap_key,
            "output": "json"
        }
        geo_resp = requests.get(geo_url, params=geo_params, timeout=8)
        geo_data = geo_resp.json()
        if geo_data.get("status") != "1":
            return None
        adcode = geo_data.get("regeocode", {}).get("addressComponent", {}).get("adcode")
        province = geo_data.get("regeocode", {}).get("addressComponent", {}).get("province")
        city = geo_data.get("regeocode", {}).get("addressComponent", {}).get("city")
        district = geo_data.get("regeocode", {}).get("addressComponent", {}).get("district")
        
        
        if not adcode:
            print("无法从经纬度获取城市代码")
            return None

        # 第二步：根据城市代码获取实时天气
        weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
        weather_params = {
            "city": adcode,  # 使用城市代码
            "key": amap_key,
            "extensions": "base"  # "base" 为实时天气，"all" 为天气预报
        }
        weather_resp = requests.get(weather_url, params=weather_params, timeout=8)
        weather_data = weather_resp.json()

        if weather_data.get("status") == "1" and weather_data.get("lives"):
            live = weather_data["lives"][0]
            # 格式化地点名称
            location_name = f"{province}{city}" if city and city != province else province
            if district and district not in location_name:
                location_name += district
            return {
                "location": location_name or "未知地区",
                "weather": live.get("weather", "未知"),
                "temperature": live.get("temperature", "N/A"),
                "humidity": live.get("humidity", "N/A"),
                "wind_direction": live.get("winddirection", "未知"),
                "wind_power": live.get("windpower", "0"),
                "report_time": live.get("reporttime", "")
            }
        else:
            print(f"获取天气数据失败: {weather_data.get('info', '未知错误')}")
            return None

    except requests.exceptions.Timeout:
        print("天气服务请求超时")
        return None
    except Exception as e:
        print(f"获取天气时发生异常: {e}")
        return None
    
# 天气预警  
def init_weather_alert_config():
    """初始化天气预警配置"""
    if 'weather_alert_config' not in st.session_state:
        st.session_state.weather_alert_config = {
            'temp_high': 35,      # 高温预警阈值（℃）
            'temp_low': 0,        # 低温预警阈值（℃）
            'wind_power': 5,      # 大风预警阈值（级）
            'humidity_high': 80,  # 高湿预警阈值（%）
            'humidity_low': 20,   # 低湿预警阈值（%）
            'enable_alerts': True  # 是否启用预警
        }
# 风力解析
def parse_wind_value(wind_str):
    """
    尝试从风力字符串中提取数字。
    例如: '≤3' -> 3.0, '4级' -> 4.0, '3~4' -> 4.0 (取最大)
    如果完全没有数字，则返回 None
    """
    if isinstance(wind_str, (int, float)):
        return float(wind_str)
    
    # 使用正则表达式寻找字符串中的所有数字（包含小数）
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", str(wind_str))
    
    if not numbers:
        return None
    
    # 如果有多个数字（比如 3~4级），取最大的那个作为预警参考
    return max(float(n) for n in numbers)      
    
def get_weather_alert(weather_info, config):
    """
    根据天气信息和用户配置生成预警信息
    """
    # print(weather_info)  # 调试输出天气信息
    if not config.get('enable_alerts', True):
        return None, "✅ 预警功能已关闭"
    alerts = []
    alert_level = "info"  # info, warning, error
    # 获取天气数值
    temp = float(weather_info.get('temperature', 0))
    humidity = int(weather_info.get('humidity', 0))
    raw_wind = weather_info.get('wind_power', "0")
    current_wind_val = parse_wind_value(raw_wind)
    weather = weather_info.get('weather', '')
    
    # 检查高温预警
    if temp >= config.get('temp_high', 35):
        alerts.append(f"🌡️ 高温预警：当前温度 {temp}℃ ≥ {config['temp_high']}℃")
        alert_level = "error"
    elif temp <= config.get('temp_low', 0):
        alerts.append(f"❄️ 低温预警：当前温度 {temp}℃ ≤ {config['temp_low']}℃")
        alert_level = "error"
    
    # 检查大风预警
    threshold_wind = float(config.get('wind_power', 5))
    if current_wind_val is not None:
        # 只有解析出数字，才进行数值比较
        if current_wind_val >= threshold_wind:
            alerts.append(f"💨 大风预警：当前风力 {raw_wind} ≥ 阈值 {threshold_wind}级")
            alert_level = "error"
    else:
        # 如果解析不出数字（比如风力信息是 "持续风"），直接作为字符串展示，不触发数值报警
        # 或者你可以根据需要添加字符串包含判断，比如 if "大风" in raw_wind:
        pass
    
    # 检查湿度预警
    if humidity >= config.get('humidity_high', 80):
        alerts.append(f"💧 高湿预警：当前湿度 {humidity}% ≥ {config['humidity_high']}%")
        if alert_level != "error":
            alert_level = "warning"
    elif humidity <= config.get('humidity_low', 20):
        alerts.append(f"🏜️ 低湿预警：当前湿度 {humidity}% ≤ {config['humidity_low']}%")
        if alert_level != "error":
            alert_level = "warning"
    # 特殊天气预警
    if '暴雨' in weather or '大暴雨' in weather:
        alerts.append(f"☔ 暴雨预警：当前天气 {weather}")
        alert_level = "error"
    elif '雪' in weather:
        alerts.append(f"❄️ 降雪预警：当前天气 {weather}")
        alert_level = "warning"
    
    if alerts:
        alert_message = " | ".join(alerts)
        return alert_level, alert_message
    else:
        return "info", "✅ 所有天气指标正常"

def display_weather_with_alerts(weather_info, location):
    """
    显示天气信息并附带预警
    """
    if not weather_info:
        st.warning("无法获取天气信息")
        return
    
    # 初始化预警配置
    init_weather_alert_config()
    config = st.session_state.weather_alert_config
    
    # 获取预警信息
    alert_level, alert_message = get_weather_alert(weather_info, config)
    
    # 格式化地点名称
    city_name = location.split('省')[-1] if '省' in location else location
    
    # 构建天气信息文本
    weather_text = f"🌤️ {city_name} 当前天气：{weather_info['weather']} | 温度 {weather_info['temperature']}℃ 湿度 {weather_info['humidity']}% 风力 {weather_info['wind_power']}级"
    
    # 根据预警级别显示不同的消息框
    if alert_level == "error":
        st.error(f"{weather_text}\n\n⚠️ **预警信息：** {alert_message}")
    elif alert_level == "warning":
        st.warning(f"{weather_text}\n\n⚠️ **注意：** {alert_message}")
    else:
        st.info(f"{weather_text}\n\n{alert_message}")
        
 
def weather_alert_settings():
    """
    天气预警设置界面
    """
    init_weather_alert_config()
    config = st.session_state.weather_alert_config
    
    st.subheader("⚙️ 天气预警阈值设置")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 🌡️ 温度预警")
        config['temp_high'] = st.number_input(
            "高温预警阈值 (℃)",
            min_value=20, max_value=50, value=config['temp_high'],
            help="当温度超过此值时触发高温预警"
        )
        config['temp_low'] = st.number_input(
            "低温预警阈值 (℃)",
            min_value=-20, max_value=10, value=config['temp_low'],
            help="当温度低于此值时触发低温预警"
        )
        
        st.markdown("#### 💨 风力预警")
        config['wind_power'] = st.number_input(
            "大风预警阈值 (级)",
            min_value=1, max_value=12, value=config['wind_power'],
            help="当风力超过此值时触发大风预警"
        )
    
    with col2:
        st.markdown("#### 💧 湿度预警")
        config['humidity_high'] = st.number_input(
            "高湿预警阈值 (%)",
            min_value=50, max_value=100, value=config['humidity_high'],
            help="当湿度超过此值时触发高湿预警"
        )
        config['humidity_low'] = st.number_input(
            "低湿预警阈值 (%)",
            min_value=0, max_value=40, value=config['humidity_low'],
            help="当湿度低于此值时触发低湿预警"
        )
    
    st.markdown("#### 🔔 预警开关")
    config['enable_alerts'] = st.toggle(
        "启用天气预警",
        value=config['enable_alerts'],
        help="关闭后将不再显示天气预警信息"
    )
    
    # 显示当前设置的示例
    st.divider()
    st.markdown("#### 📋 当前预警规则示例")
    
    example_weather = {
        'weather': '晴',
        'temperature': config['temp_high'] + 1,
        'humidity': config['humidity_high'] + 5,
        'wind_power': config['wind_power']
    }
    
    level, message = get_weather_alert(example_weather, config)
    st.caption(f"当温度={example_weather['temperature']}℃、湿度={example_weather['humidity']}%、风力={example_weather['wind_power']}级时：")
    if level == "error":
        st.error(f"⚠️ {message}")
    elif level == "warning":
        st.warning(f"⚠️ {message}")
    else:
        st.success(f"✅ {message}")
    
    if st.button("💾 保存预警设置", use_container_width=True):
        st.toast("✅ 预警设置已保存", icon="✅")
        st.rerun()