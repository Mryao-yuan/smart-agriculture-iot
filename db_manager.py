import pymysql
import streamlit as st
from datetime import datetime

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
            
            # 2. 传感器历史表 (增加索引以优化性能)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_history (
                    history_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    sensor_id BIGINT,
                    val DOUBLE,
                    switcher TINYINT,
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
    """
    同步嵌套数据到 TiDB
    注意：SQL 语句中的 ? 全部替换为 %s
    """
    if json_response.get("flag") != "00" or not json_response.get("dataList"):
        return

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            for device in json_response.get("dataList", []):
                # 更新设备状态
                cursor.execute('''
                    INSERT INTO devices (device_id, device_no, gh_name, is_line, is_alarms, lat, lng)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                    is_line=VALUES(is_line), is_alarms=VALUES(is_alarms), last_updated=CURRENT_TIMESTAMP
                ''', (
                    device.get("id"), device.get("deviceNo"), device.get("deviceName"),
                    device.get("isLine"), device.get("isAlarms"), device.get("lat"), device.get("lng")
                ))

                # 更新传感器历史
                for sensor in (device.get("sensorsList") or []):
                    if sensor.get("updateDate"):
                        # 使用 INSERT IGNORE 防止重复
                        cursor.execute('''
                            INSERT IGNORE INTO sensor_history (sensor_id, val, switcher, add_time)
                            VALUES (%s, %s, %s, %s)
                        ''', (
                            sensor.get("id"), 
                            float(sensor.get("value") or 0), 
                            int(sensor.get("switcher") or 0),
                            sensor.get("updateDate")
                        ))
        conn.commit()
    except Exception as e:
        print(f"TiDB Sync Error: {e}")
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