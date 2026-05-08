import json
import requests
import re
import streamlit as st


def convert_device_data(device_tuples):
    """
    将设备元组数据转换为 Streamlit 可展示的字典格式
    """
    converted_data = []
    
    for device in device_tuples:
        print("原始设备数据:", device)  # 调试输出
        
        device_dict = {
            'deviceId': device[0],    # 设备ID
            'deviceName': device[2],  # 设备名称
            'deviceNo': device[1],    # 设备编号
            'lat': device[3],         # 纬度
            'lng': device[4],         # 经度
            'isAlarms': device[8],     # 告警状态
            'isDelete': device[9],     # 删除状态
            'isLine': device[10],      # 假设 index 8 是在线状态
        }
        converted_data.append(device_dict)
    return converted_data



def get_sorted_devices(device_list):
    """
    将设备列表按照名称开头的数字进行排序
    """
    def extract_num(name):
        match = re.search(r'^(\d+)', str(name))
        return int(match.group(1)) if match else 9999
    
    return sorted(device_list, key=lambda x: extract_num(x.get('deviceName', '')))



# # 假设这是你后台拉取数据的某个定时任务或处理函数
# def check_and_alert(device_data, alert_config):
#     gh_name = device_data['deviceName']
#     temp = get_sensor_info(device_data['sensorsList'], "空温") 
#     is_alarm = device_data['isAlarms']

#     # 触发条件：系统标记报警，或者温度大于设定的 35 度
#     if is_alarm == 1 or float(temp) > 35.0:
#         alert_msg = f"当前温度 {temp}℃，超过设定阈值！"
        
#         # 检查用户是否开启了短信推送
#         if alert_config.get("sms_enabled"):
#             phone = alert_config.get("phone")
#             send_aliyun_sms(phone, gh_name, temp)
            
#         # 检查用户是否开启了微信推送
#         if alert_config.get("wechat_enabled"):
#             send_wechat_bot(gh_name, alert_msg)

def process_api_response(data_list):
    """
    处理API响应数据，直接保存为字典格式供Streamlit使用
    """
    devices_for_streamlit = []
    devices_for_db = []  # 如果需要数据库操作
    sensors_for_db = []
    
    for device in data_list:
        # ========== 为Streamlit准备的字典（直接可用）==========
        streamlit_device = {
            'deviceName': device.get("deviceName"),
            'deviceNo': device.get("deviceNo"),
            'isLine': device.get("isLine", 0),
            'isAlarms': device.get("isAlarms", 0),
            'latitude': device.get("lat", 0.0),
            'longitude': device.get("lng", 0.0),
            'lastTime': device.get("heartbeatDate"),  # 最后通讯时间
            'sensorsList': []
        }
        
        # 处理传感器数据
        sensors_list = device.get("sensorsList", [])
        for sensor in sensors_list:
            sensor_type = sensor.get("sensorTypeId")
            raw_value = sensor.get("value")
            raw_switch = sensor.get("switcher")
            
            # 处理不同类型的传感器值
            if sensor_type == 1:  # 数值型
                value = str(float(raw_value)) if raw_value else "0"
            elif sensor_type in [2, 5, 6]:  # 开关/档位
                value = str(int(raw_switch)) if raw_switch else "0"
            elif sensor_type == 3:  # GPS
                value = json.dumps({
                    "lat": sensor.get("lat"),
                    "lng": sensor.get("lng")
                })
            else:
                value = str(raw_value) if raw_value else ""
            
            streamlit_sensor = {
                'sensorName': sensor.get("sensorName"),
                'value': value,
                'unit': sensor.get("unit", ""),
                'sensorTypeId': sensor_type,
                'isAlarms': sensor.get("isAlarms", 0)
            }
            streamlit_device['sensorsList'].append(streamlit_sensor)
        
        devices_for_streamlit.append(streamlit_device)
        
        # ========== 为数据库准备的元组（可选）==========
        devices_for_db.append((
            device.get("id"),
            device.get("deviceNo"),
            device.get("deviceName"),
            device.get("lat", 0.0),
            device.get("lng", 0.0),
            # ... 其他数据库字段
        ))
    
    return devices_for_streamlit, devices_for_db, sensors_for_db



def data_process(data):
    r'''处理从平台拉取的原始数据，返回一个结构化的列表或字典，方便后续在前端展示或存入数据库。
    '''
    data_list = data.get("dataList", [])

    devices_to_upsert = []
    sensors_to_upsert = []
    # history_to_insert = []
    
    for device in data_list:
        device_id = device.get("id")
        # ================= 设备 =================
        devices_to_upsert.append((
            device_id,
            device.get("deviceNo"),
            device.get("deviceName"),
            device.get("lat", 0.0),
            device.get("lng", 0.0),
            device.get("createDate"),
            device.get("defaultTimescale"),
            device.get("icoUrl"),
            device.get("isAlarms", 0),
            device.get("isDelete", 0),
            device.get("isLine", 0),
            device.get("linktype"),
            device.get("userId"),
            device.get("userName")
        ))

        sensors_list = device.get("sensorsList")
        if not sensors_list:
            continue

        for sensor in sensors_list:
            sensor_id = sensor.get("id")
            sensor_type = sensor.get("sensorTypeId")
            raw_value = sensor.get("value")
            raw_switch = sensor.get("switcher")
            value = None
            if sensor_type == 1:
                # 数值型
                value = str(float(raw_value)) if raw_value else "0"
            elif sensor_type in [2, 5, 6]:
                # 开关 / 档位
                value = str(int(raw_switch)) if raw_switch else "0"
            elif sensor_type == 3:
                # GPS
                value = json.dumps({
                    "lat": sensor.get("lat"),
                    "lng": sensor.get("lng")
                })
            elif sensor_type == 4:
                # 图片
                value = raw_value or ""
            elif sensor_type == 8:
                # 字符串
                value = raw_value or ""
            else:
                value = str(raw_value) if raw_value else ""
            # ================= 传感器元数据 =================
            sensors_to_upsert.append((
                sensor_id,
                device_id,
                sensor.get("sensorName"),
                sensor.get("sensorTypeId"),
                value,
                sensor.get("unit"),
                sensor.get("flag"),
                sensor.get("decimalPlacse"),
                sensor.get("heartbeatDate"),
                sensor.get("isAlarms", 0),
                sensor.get("isDelete", 0),
                sensor.get("isLine", 0),
                sensor.get("isMapping", 0),
                sensor.get("lat", 0.0),
                sensor.get("lng", 0.0),
                sensor.get("ordernum"),
                sensor.get("sensorMapping"),
                sensor.get("userId"),
                sensor.get("updateDate"),
            ))
                
    return devices_to_upsert, sensors_to_upsert



# def display_devices_grid(devices_list):
#     """网格形式展示设备 - 直接使用API响应数据"""
    
#     # 每行显示3个设备
#     cols_per_row = 3
    
#     for i in range(0, len(devices_list), cols_per_row):
#         cols = st.columns(cols_per_row)
        
#         for j, col in enumerate(cols):
#             idx = i + j
#             if idx < len(devices_list):
#                 device = devices_list[idx]  # 直接是字典格式
                
#                 with col:
#                     # 直接从字典取值，无需索引
#                     device_name = device.get('deviceName', '未知设备')
#                     device_no = device.get('deviceNo', 'N/A')
#                     last_time = device.get('createDate', '')
#                     is_online = device.get('isLine', 0) == 1  # 1=在线, 0=离线
#                     has_alarm = device.get('isAlarms', 0) == 1
                    
#                     with st.container(border=True):
#                         st.markdown(f"### {device_name}")
#                         st.markdown(f"**编号：** `{device_no}`")
#                         st.markdown(f"**时间：** {last_time[:10] if last_time else 'N/A'}")
                        
#                         # 状态标签
#                         status_cols = st.columns(2)
#                         with status_cols[0]:
#                             if is_online:
#                                 st.success("🟢 在线")
#                             else:
#                                 st.error("🔴 离线")
#                         with status_cols[1]:
#                             if has_alarm:
#                                 st.warning("⚠️ 告警")
#                             else:
#                                 st.info("✅ 正常")


# 定义设备展示函数
def display_devices_grid(devices_list):
    """网格形式展示设备 - 直接使用API响应数据"""
    if not devices_list:
        st.info("暂无设备数据，请点击「同步云端最新数据」获取设备信息")
        return
    
    # 每行显示3个设备
    cols_per_row = 3
    
    for i in range(0, len(devices_list), cols_per_row):
        cols = st.columns(cols_per_row)
        
        for j, col in enumerate(cols):
            idx = i + j
            if idx < len(devices_list):
                device = devices_list[idx]
                with col:
                    device_name = device.get('deviceName', '未知设备')
                    device_no = device.get('deviceNo', 'N/A')
                    last_time = device.get('createDate', '')
                    is_online = device.get('isLine', 0) == 1
                    has_alarm = device.get('isAlarms', 0) == 1
                    
                    with st.container(border=True):
                        st.markdown(f"### 📟 {device_name}")
                        st.markdown(f"**编号：** `{device_no}`")
                        if last_time:
                            st.markdown(f"**时间：** {last_time[:10] if last_time else 'N/A'}")
                        # 状态标签
                        status_cols = st.columns(2)
                        with status_cols[0]:
                            if is_online:
                                st.success("🟢 在线")
                            else:
                                st.error("🔴 离线")
                        with status_cols[1]:
                            if has_alarm:
                                st.warning("⚠️ 告警")
                            else:
                                st.info("✅ 正常")
                        
                        # 显示传感器数据
                        sensors_list = device.get('sensorsList', [])
                        if sensors_list:
                            st.divider()
                            st.markdown("**传感器数据：**")
                            for sensor in sensors_list:
                                sensor_name = sensor.get('sensorName', '未知')
                                value = sensor.get('value', 'N/A')
                                unit = sensor.get('unit', '')
                                st.metric(sensor_name, f"{value} {unit}")


###### ============ 12 基于经纬度查询天气
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
    
    
# 钉钉网址确认
def dingding_webhook_check(webhook_url):
    payload = {
    "msgtype": "text",
    "text": {
        "content": "预警：测试消息"
    }}

    response = requests.post(webhook_url, json=payload)
    return response.json()['errmsg'] != "ok"

def user_webhook_check(webhook_url):
    if not webhook_url.startswith("https://oapi.dingtalk.com/robot/send?access_token="):
        st.error("❌ Webhook 地址必须以 https://oapi.dingtalk.com/robot/send?access_token= 开头")
        return False
    token_part = webhook_url.split("access_token=")[-1]
    if len(token_part) != 64:
        st.error("❌ Webhook 地址中的 access_token 长度不正确，应为64位")
        return False
    st.success("✅ Webhook 地址格式正确")
    return True



############# 文本操作
# 温室名排序
def extract_gh_num(name):
    # 使用正则表达式提取字符串开头的数字，例如从 "01号青海..." 提取出 1
    match = re.search(r'^(\d+)', str(name))
    return int(match.group(1)) if match else 9999