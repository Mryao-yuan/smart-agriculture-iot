import pymysql
import streamlit as st
import time
import json
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
    """初始化 TiDB 云端数据库并自动建表（适配嵌套同步逻辑）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 创建报警配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alert_config (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    target_gh VARCHAR(100),
                    max_temp DOUBLE,
                    min_temp DOUBLE,
                    sms_enabled TINYINT(1),
                    phone VARCHAR(20),
                    wechat_enabled TINYINT(1),
                    pushplus_token VARCHAR(255)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            
            # 2. 创建农事工单记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS work_orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    gh_name VARCHAR(100),
                    task_type VARCHAR(50),
                    operator VARCHAR(50),
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')
            
            # 3. 设备表 (与 sync_iot_nested_data 字段完全对应)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS devices (
                    device_id BIGINT PRIMARY KEY, 
                    device_no VARCHAR(50),
                    gh_name VARCHAR(100),
                    lat DOUBLE,
                    lng DOUBLE,
                    create_date DATETIME,
                    default_timescale INT,
                    ico_url VARCHAR(255),
                    is_alarms TINYINT,
                    is_delete TINYINT,
                    is_line TINYINT,
                    link_type VARCHAR(50),
                    user_id BIGINT,
                    user_name VARCHAR(50),
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')

            # 4. 传感器元数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensors (
                    sensor_id BIGINT PRIMARY KEY,
                    device_id BIGINT,
                    sensor_name VARCHAR(100),
                    sensor_type_id INT,
                    unit VARCHAR(20),
                    flag VARCHAR(20),
                    decimal_places INT,
                    heartbeat_date DATETIME, -- 补全 sync 逻辑中的字段
                    is_alarms TINYINT,
                    is_delete TINYINT,
                    is_line TINYINT,
                    is_mapping TINYINT,
                    lat DOUBLE,
                    lng DOUBLE,
                    order_num INT,
                    sensor_mapping VARCHAR(100),
                    user_id BIGINT,
                    last_update DATETIME
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')

            # 5. 传感器历史时序数据表
            # 注意：TiDB 自动为 UNIQUE 约束创建索引，不需额外手动创建 idx_sensor_time
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_history (
                    history_id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    sensor_id BIGINT,
                    value VARCHAR(255),
                    add_time DATETIME,
                    UNIQUE KEY uk_sensor_time (sensor_id, add_time)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            ''')        
        conn.commit()
        print("✅ TiDB 云端数据库初始化成功，所有表结构已同步")
    except Exception as e:
        print(f"❌ 初始化数据库失败: {e}")
        conn.rollback()
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

def get_sensor_history_tidb(sensor_id, start_time, end_time,fallback_limit=20):
    """
    从远端 TiDB 获取传感器历史数据
    :param sensor_id: 传感器ID
    :param start_time: 起始时间 (字符串 '2023-01-01 00:00:00' 或 datetime对象)
    :param end_time: 结束时间
    """
    # 使用之前定义的获取连接函数
    conn = get_connection() 
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # --- 1. 尝试按时间范围查询 ---
            sql_range = """
                SELECT add_time, value
                FROM sensor_history
                WHERE sensor_id = %s
                AND add_time BETWEEN %s AND %s
                ORDER BY add_time ASC
            """
            cursor.execute(sql_range, (sensor_id, start_time, end_time))
            rows = cursor.fetchall()
            # --- 2. 自动保底：如果范围查询结果为空，取最新数据 ---
            if not rows:
                sql_fallback = """
                    SELECT add_time, value FROM sensor_history
                    WHERE sensor_id = %s ORDER BY add_time DESC LIMIT %s
                """
                cursor.execute(sql_fallback, (sensor_id, fallback_limit))
                rows = cursor.fetchall()
                rows.reverse()
                for r in rows: r['is_fallback'] = True
            return rows
    except Exception as e:
        print(f"❌ 数据库查询失败: {e}")
        return []
    finally:
        conn.close()
        
def get_sensor_history_df(sensor_id, start_time, end_time):
    """
    使用 Pandas 直接从 TiDB 读取并返回 DataFrame，方便 Streamlit 绘图
    """
    conn = get_connection()
    try:
        sql = """
            SELECT add_time, value
            FROM sensor_history
            WHERE sensor_id = %s
            AND add_time BETWEEN %s AND %s
            ORDER BY add_time
        """
        # pd.read_sql 会自动处理连接和关闭（部分版本建议配合 sqlalchemy）
        df = pd.read_sql(sql, conn, params=(sensor_id, start_time, end_time))
        return df
    finally:
        conn.close()

def get_compare_data(sensor_name, start_time):
    conn = get_connection()
    query = """
        SELECT 
            d.gh_name, 
            h.add_time, 
            CAST(h.value AS DECIMAL(10,2)) as val
        FROM sensor_history h
        JOIN sensors s ON h.sensor_id = s.sensor_id
        JOIN devices d ON s.device_id = d.device_id
        WHERE s.sensor_name = %s 
          AND h.add_time >= %s
        ORDER BY h.add_time ASC
    """
    import pandas as pd
    df = pd.read_sql(query, conn, params=(sensor_name, start_time))
    conn.close()
    return df