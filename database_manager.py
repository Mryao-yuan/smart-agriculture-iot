import sqlite3
from datetime import datetime
import json
from config import *
import pandas as pd
import time

def init_db():
    """初始化数据库并自动建表"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. 创建报警配置表 (全局只有一条记录，或者每个大棚一条)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alert_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_gh TEXT,
            max_temp REAL,
            min_temp REAL,
            sms_enabled INTEGER,
            phone TEXT,
            wechat_enabled INTEGER,
            pushplus_token TEXT
        )
    ''')
    
    # 2. 创建农事工单记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gh_name TEXT,
            task_type TEXT,
            operator TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 3. 设备表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            device_id INTEGER PRIMARY KEY, 
            device_no TEXT UNIQUE,
            gh_name TEXT,
            lat REAL,
            lng REAL,
            create_date TEXT,
            default_timescale INTEGER,
            ico_url TEXT,
            is_alarms INTEGER,
            is_delete INTEGER,
            is_line INTEGER,
            link_type TEXT,
            user_id INTEGER,
            user_name TEXT,
            last_updated TEXT
        )
    ''')

    # 4. 传感器元数据表 (Sensor)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensors (
        sensor_id INTEGER PRIMARY KEY,
        device_id INTEGER,
        sensor_name TEXT,
        sensor_type_id INTEGER,
        unit TEXT,
        flag TEXT,
        decimal_places INTEGER,
        is_alarms INTEGER,
        is_delete INTEGER,
        is_line INTEGER,
        is_mapping INTEGER,
        lat REAL,
        lng REAL,
        order_num INTEGER,
        sensor_mapping TEXT,
        user_id INTEGER,
        last_update TEXT,
        FOREIGN KEY(device_id) REFERENCES devices(device_id)
    )
    ''')

    # 5. 传感器历史时序数据表 (History) - 数据量最大的一张表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER,
            value TEXT,
            add_time TEXT,
            FOREIGN KEY(sensor_id) REFERENCES sensors(sensor_id),
            UNIQUE(sensor_id, add_time)
    )
    ''')
    
    # 【性能优化】为历史表创建组合索引，画“某传感器某时间段曲线”时查询速度提升 100 倍
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_time ON sensor_history(sensor_id, add_time)')
    
    conn.commit()
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

            # ================= 传感器元数据 =================
            sensors_to_upsert.append((
                sensor_id,
                device_id,
                sensor.get("sensorName"),
                sensor.get("sensorTypeId"),
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
                sensor.get("updateDate")
            ))
            # ================= 核心：统一 value =================
            sensor_type = sensor.get("sensorTypeId")
            raw_value = sensor.get("value")
            raw_switch = sensor.get("switcher")

            value = None

            try:
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

            except Exception:
                value = ""

            update_date = sensor.get("updateDate")

            if update_date and value is not None:
                history_to_insert.append((
                    sensor_id,
                    value,
                    sensor.get("updateDate")                       # 设备时间
                ))

    # ================= 写数据库 =================
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        # 设备
        cursor.executemany('''
            REPLACE INTO devices (
                device_id, device_no, gh_name, lat, lng,
                create_date, default_timescale, ico_url,
                is_alarms, is_delete, is_line,
                link_type, user_id, user_name,
                last_updated
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', devices_to_upsert)

        # 传感器
        cursor.executemany('''
            REPLACE INTO sensors (
                sensor_id, device_id, sensor_name, sensor_type_id, unit,
                flag, decimal_places, heartbeat_date,
                is_alarms, is_delete, is_line, is_mapping,
                lat, lng, order_num,
                sensor_mapping, user_id, last_update
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sensors_to_upsert)

        # 历史数据
        cursor.executemany('''
            INSERT OR IGNORE INTO sensor_history (sensor_id, value, add_time)
            VALUES (?, ?, ?)
        ''', history_to_insert)

        conn.commit()
        print(f"✅ 时间：{time.strftime('%Y-%m-%d %H:%M:%S')} \
            设备:{len(devices_to_upsert)} 传感器:{len(sensors_to_upsert)} 历史:{len(history_to_insert) }")

    except Exception as e:
        print("❌ 数据库错误:", e)
        conn.rollback()
    finally:
        conn.close()




# ==================== 报警配置 CRUD ====================
def save_alert_config(target_gh, max_temp, min_temp, sms_enabled, phone, wechat_enabled, pushplus_token):
    """保存或更新报警配置 (这里为了简单，我们采用覆盖写入的方式，保持ID为1)"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 先检查是否已经有配置了
    cursor.execute("SELECT id FROM alert_config WHERE id = 1")
    if cursor.fetchone():
        # 更新
        cursor.execute('''
            UPDATE alert_config 
            SET target_gh=?, max_temp=?, min_temp=?, sms_enabled=?, phone=?, wechat_enabled=?, pushplus_token=?
            WHERE id = 1
        ''', (target_gh, max_temp, min_temp, int(sms_enabled), phone, int(wechat_enabled), pushplus_token))
    else:
        # 插入
        cursor.execute('''
            INSERT INTO alert_config (id, target_gh, max_temp, min_temp, sms_enabled, phone, wechat_enabled, pushplus_token)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ''', (target_gh, max_temp, min_temp, int(sms_enabled), phone, int(wechat_enabled), pushplus_token))
        
    conn.commit()
    conn.close()



def get_alert_config():
    """读取报警配置"""
    conn = sqlite3.connect(DB_NAME)
    # 返回字典格式，方便前端调用
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alert_config WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return {} # 如果没有数据，返回空字典

# ==================== 物联网数据写入逻辑 ====================

def upsert_devices(devices_json_list):
    """
    处理获取到的【设备列表】数据，更新设备台账
    """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    for d in devices_json_list:
        device_id = d.get("id")
        device_no = d.get("deviceNo")
        gh_name = d.get("deviceName", "未知大棚")
        is_line = d.get("isLine", 0)
        is_alarms = d.get("isAlarms", 0)
        lat = d.get("lat", 36.73291)
        lng = d.get("lng", 101.74776)
        
        # REPLACE INTO：有则更新在线状态，无则插入新设备
        cursor.execute('''
            REPLACE INTO devices (device_id, device_no, gh_name, is_line, is_alarms, lat, lng, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (device_id, device_no, gh_name, is_line, is_alarms, lat, lng))
    conn.commit()
    conn.close()

# ==================== 物联网数据读取逻辑 (给 app.py 用) ====================

def get_devices():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT device_id, gh_name 
        FROM devices
        WHERE is_delete = 0
    """).fetchall()

    conn.close()
    return [dict(r) for r in rows]

def get_sensors_by_device(device_id):
    r'''
    获取数值类型的传感器数据
    '''
    #  AND sensor_type_id = 1 筛选数据类型
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT sensor_id, sensor_name, sensor_type_id,unit
        FROM sensors
        WHERE device_id = ?
    """, (device_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_sensor_history(sensor_id, start_time, end_time):
    r'''
    获取传感器历史数据
    '''
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT add_time, value
        FROM sensor_history
        WHERE sensor_id = ?
        AND add_time BETWEEN ? AND ?
        ORDER BY add_time
    """, (sensor_id, start_time, end_time)).fetchall()

    conn.close()
    return [dict(r) for r in rows]


# 读取数据库
def get_devices_status():
    conn = sqlite3.connect("Smart_Agriculture.db")

    df = pd.read_sql("""
        SELECT 
            device_id,
            gh_name,
            lat,
            lng,
            is_alarms,
            is_delete,
            is_line
        FROM devices
    """, conn)

    conn.close()

    # ================= 状态判断 =================
    def calc_status(row):
        if row["is_delete"] == 1:
            return None

        if row["is_alarms"] == 1:
            return "alarm"
        elif row["is_line"] == 0:
            return "offline"
        else:
            return "normal"

    df["status"] = df.apply(calc_status, axis=1)

    df = df.dropna()

    return df

# ================= 显示地图 =================
# df = get_devices_status()

# st.subheader("📍 温室位置分布")

# st.map(df.rename(columns={
#     "lat": "latitude",
#     "lng": "longitude"
# }))


# =========================================================================
# 当直接运行这个脚本时，初始化数据库表
if __name__ == "__main__":
    init_db()
    print(f"数据库 {DB_NAME} 初始化成功！表已建立。")