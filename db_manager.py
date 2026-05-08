import pymysql
import streamlit as st
from datetime import datetime

# connect with TiDB Cloud using pymysql
# 从 secrets 读取配置
TIDB_CONFIG = st.secrets["tidb"]

def get_connection():
    """获取 TiDB Cloud 连接"""
    return pymysql.connect(
        host=TIDB_CONFIG["host"],
        port=TIDB_CONFIG["port"],
        user=TIDB_CONFIG["user"],
        password=TIDB_CONFIG["password"],
        database=TIDB_CONFIG["database"],
        ssl_verify_cert=True, # TiDB Cloud 必须开启 SSL
        ssl_verify_identity=True,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor # 这样返回的结果就是字典格式，兼容你之前的逻辑
    )

def init_db():
    """初始化云端数据库表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 设备表 (注意：SQLite 的 AUTOINCREMENT 在 MySQL 里是 AUTO_INCREMENT)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    device_id BIGINT PRIMARY KEY,
                    device_no VARCHAR(50) UNIQUE,
                    gh_name VARCHAR(100),
                    is_line TINYINT,
                    is_alarms TINYINT,
                    lat DOUBLE,
                    lng DOUBLE,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ''')
            
            # 2. 传感器元数据表 (你遗漏的这张表补上了)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensors (
                    sensor_id BIGINT PRIMARY KEY, device_id BIGINT, sensor_name VARCHAR(100),
                    sensor_type_id INT, unit VARCHAR(20), flag VARCHAR(20), decimal_places INT,
                    heartbeat_date DATETIME, is_alarms TINYINT, is_delete TINYINT, is_line TINYINT,
                    is_mapping TINYINT, lat DOUBLE, lng DOUBLE, order_num INT,
                    sensor_mapping VARCHAR(100), user_id BIGINT, last_update DATETIME
                )
            ''')
            
            
            # 2. 传感器历史表 (增加索引以优化性能)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_history (
                    history_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    sensor_id BIGINT,
                    value VARCHAR(255), 
                    add_time DATETIME,
                    UNIQUE KEY uk_sensor_time (sensor_id, add_time)
                )
            ''')
            # 索引对云数据库非常重要
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_time ON sensor_history(sensor_id, add_time)')
            
        conn.commit()
    finally:
        conn.close()

def sync_iot_nested_data(json_response):
    if json_response.get("flag") != "00" or not json_response.get("dataList"):
        print("未获取到有效数据或数据为空")
        return

    data_list = json_response.get("dataList", [])

    devices_to_upsert = []
    sensors_to_upsert = []
    history_to_insert = []

    for device in data_list:
        device_id = device.get("id")
        # ================= 1. 组装设备 =================
        devices_to_upsert.append((
            device_id, device.get("deviceNo"), device.get("deviceName"),
            device.get("lat", 0.0), device.get("lng", 0.0), device.get("createDate"),
            device.get("defaultTimescale"), device.get("icoUrl"), device.get("isAlarms", 0),
            device.get("isDelete", 0), device.get("isLine", 0), device.get("linktype"),
            device.get("userId"), device.get("userName")
        ))

        sensors_list = device.get("sensorsList")
        if not sensors_list:
            continue

        for sensor in sensors_list:
            sensor_id = sensor.get("id")

            # ================= 2. 组装传感器元数据 =================
            sensors_to_upsert.append((
                sensor_id, device_id, sensor.get("sensorName"), sensor.get("sensorTypeId"),
                sensor.get("unit"), sensor.get("flag"), sensor.get("decimalPlacse"),
                sensor.get("heartbeatDate"), sensor.get("isAlarms", 0), sensor.get("isDelete", 0),
                sensor.get("isLine", 0), sensor.get("isMapping", 0), sensor.get("lat", 0.0),
                sensor.get("lng", 0.0), sensor.get("ordernum"), sensor.get("sensorMapping"),
                sensor.get("userId"), sensor.get("updateDate")
            ))
            
            # ================= 3. 核心：统一 value =================
            sensor_type = sensor.get("sensorTypeId")
            raw_value = sensor.get("value")
            raw_switch = sensor.get("switcher")

            value = None

            try:
                if sensor_type == 1:
                    value = str(float(raw_value)) if raw_value else "0"
                elif sensor_type in [2, 5, 6]:
                    value = str(int(raw_switch)) if raw_switch else "0"
                elif sensor_type == 3:
                    value = json.dumps({"lat": sensor.get("lat"), "lng": sensor.get("lng")})
                elif sensor_type in [4, 8]:
                    value = str(raw_value) if raw_value else ""
                else:
                    value = str(raw_value) if raw_value else ""
            except Exception:
                value = ""

            update_date = sensor.get("updateDate")
            if update_date and value is not None:
                history_to_insert.append((sensor_id, value, update_date))

    # ================= 写 TiDB 数据库 (使用 PyMySQL) =================
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 设备入库 (TiDB 完全兼容 REPLACE INTO，所有 ? 改为 %s)
            if devices_to_upsert:
                cursor.executemany('''
                    REPLACE INTO devices (
                        device_id, device_no, gh_name, lat, lng,
                        create_date, default_timescale, ico_url,
                        is_alarms, is_delete, is_line,
                        link_type, user_id, user_name, last_updated
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ''', devices_to_upsert)
            if sensors_to_upsert:
                cursor.executemany('''
                    REPLACE INTO sensors (
                        sensor_id, device_id, sensor_name, sensor_type_id, unit,
                        flag, decimal_places, heartbeat_date,
                        is_alarms, is_delete, is_line, is_mapping,
                        lat, lng, order_num,
                        sensor_mapping, user_id, last_update
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', sensors_to_upsert)
            # 历史数据入库 (TiDB 中用 INSERT IGNORE 替代 SQLite 的 INSERT OR IGNORE)
            if history_to_insert:
                cursor.executemany('''
                    INSERT IGNORE INTO sensor_history (sensor_id, value, add_time)
                    VALUES (%s, %s, %s)
                ''', history_to_insert)

        conn.commit()
        print(f"✅ 时间：{time.strftime('%Y-%m-%d %H:%M:%S')} | 设备:{len(devices_to_upsert)} | 传感器:{len(sensors_to_upsert)} | 历史:{len(history_to_insert)}")

    except Exception as e:
        print(f"❌ 云数据库写入错误: {e}")
        conn.rollback()
    finally:
        conn.close()

def get_sensor_history_by_time(sensor_id, start_str, end_str):
    """从 TiDB 读取历史数据"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT add_time, val FROM sensor_history WHERE sensor_id = %s AND add_time BETWEEN %s AND %s ORDER BY add_time ASC"
            cursor.execute(sql, (sensor_id, start_str, end_str))
            return cursor.fetchall() # DictCursor 会直接返回字典列表
    finally:
        conn.close()