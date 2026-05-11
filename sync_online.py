import requests
import pymysql
import json
from datetime import datetime, timedelta
import re
import db_manager
from config import *
from utils.iot_client import IotClient  

ALERT_COOLDOWN_HOURS = 5


def run_single_sync():
    print("🚀 [云端调度] 开始执行单次 IoT 数据同步...")
    client = IotClient()
    login_res = client.login(USERNAME, PASSWORD, API_KEY)
    print("🔐 正在登录...")
    if login_res.get("flag") != "00":
        print("❌ 登录失败:")
        return
    token_res = client.get_access_token(USERNAME, PASSWORD)
    if token_res.get("flag") != "00":
        print("❌ 获取访问令牌失败:")
        return
    response = client.get_devices_sensor_datas()
    if response.get("flag") != "00" or not response.get("dataList"):
        print("未获取到有效数据或数据为空")
        return
    data = response.get("dataList", [])
    if data:
        snapshot = db_manager.sync_iot_nested_data(data)
        print("✅ [云端调度] 单次同步入库完成！")
        if snapshot:
            print(f"🔍 正在巡检 {len(snapshot)} 个传感器节点...")
            check_alerts_logic(snapshot)
    else:
        print("⚠️ [云端调度] 未获取到有效数据。")

def send_dingtalk_msg(webhook, data, reason):
    """执行钉钉 Markdown 推送"""
    if not webhook: return
    headers = {'Content-Type': 'application/json'}
    if data['sensor_type'] == 1: # 数值类型报警
        current_status_text = f"<font color='#dd0000'>**{data['value']} {data['unit']}**</font>"
        metric_label = "检测数值"
    else: # 开关/状态类型：显示状态描述
        # 假设 1 为开启/异常，0 为关闭/正常，或者直接显示原始状态字符
        status_alias = "⚠️ 异常状态" if data['value'] == "1" else "ℹ️ 状态变更"
        current_status_text = f"<font color='#ff8c00'>**{status_alias} ({data['value']})**</font>"
        metric_label = "当前状态"
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "环境预警",
            "text": f"### 🚨 实时环境预警\n"
                    f"--- \n"
                    f"**📍 报警位置**：{data['device_name']} \n\n"
                    f"**📊 监控对象**：{data['sensor_name']} \n\n"
                    f"**‼️ {metric_label}**：{current_status_text} \n\n"
                    f"**⚠️ 异常原因**：{reason} \n\n"
                    f"**⏰ 采集时间**：{data['data_time']} \n\n"
                    f"--- \n"
                    f"请相关管理人员及时排查！"
        }
    }
    try:
        requests.post(webhook, data=json.dumps(payload), headers=headers, timeout=5)
        print(f"🔔 已向钉钉推送报警：{data['device_name']}-{data['sensor_name']}")
    except:
        print(f"⚠️ 钉钉推送失败: {data['device_name']}-{data['sensor_name']}")
        pass

def send_recovery_msg(webhook, data, message):
    """执行钉钉 Markdown 恢复通知"""
    if not webhook:
        return
    headers = {'Content-Type': 'application/json'}
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": "环境恢复通知",
            "text": f"### ✅ 环境恢复通知\n"
                    f"--- \n"
                    f"**📍 恢复位置**：{data['device_name']} \n\n"
                    f"**📊 监控对象**：{data['sensor_name']} \n\n"
                    f"**当前状态**：<font color='#16a34a'>**已恢复正常**</font> \n\n"
                    f"**说明**：{message} \n\n"
                    f"**⏰ 采集时间**：{data['data_time']} \n\n"
                    f"--- \n"
                    f"系统已自动重置该报警状态。"
        }
    }
    try:
        requests.post(webhook, data=json.dumps(payload), headers=headers, timeout=5)
        print(f"✅ 已发送恢复通知：{data['device_name']}-{data['sensor_name']}")
    except:
        print(f"⚠️ 恢复通知发送失败: {data['device_name']}-{data['sensor_name']}")
        pass

def normalize_metric_name(sensor_name, sensor_type):
    if sensor_type == 1:
        return re.sub(r'^\d+[号组]', '', sensor_name).strip()
    return sensor_name

def evaluate_rule_status(rule, data):
    sensor_type = data.get('sensor_type')
    try:
        current_value = float(data['value'])
    except Exception:
        return "normal", "", None

    if sensor_type == 1:
        if rule['max_val'] is not None and current_value > float(rule['max_val']):
            return "abnormal", f"数值超过上限 {rule['max_val']}", current_value
        if rule['min_val'] is not None and current_value < float(rule['min_val']):
            return "abnormal", f"数值低于下限 {rule['min_val']}", current_value
        return "normal", "数值已恢复至阈值范围内", current_value

    if sensor_type == 2:
        if rule['max_val'] is not None and current_value == float(rule['max_val']):
            state_desc = "触发/异常/开启" if current_value == 1.0 else "正常/关闭"
            return "abnormal", f"设备状态变为设定目标: {int(current_value)} ({state_desc})", current_value
        return "normal", "设备状态已恢复至非报警目标值", current_value

    return "normal", "", current_value

# ==================== 2. 预警巡检逻辑 ====================
def check_alerts_logic(snapshot):
    """
    基于本次同步的数据进行预警判定
    current_sync_data 格式: [{'device_name': 'xx', 'sensor_name': 'xx', 'value': 10}, ...]
    """
    conn = db_manager.get_connection()
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT * FROM alert_rules")
            rules = cursor.fetchall()
            if not rules:
                return

            cursor.execute("SELECT * FROM alert_state")
            alert_states = cursor.fetchall()
            state_map = {(row['target_gh'], row['metric_name']): row for row in alert_states}
            now = datetime.now()

            for data in snapshot:
                try:
                    sensor_type = data.get('sensor_type')
                    metric_name = normalize_metric_name(data['sensor_name'], sensor_type)
                    for rule in rules:
                        if rule['target_gh'] != data['device_name'] or rule['metric_name'] != metric_name:
                            continue

                        status, message, current_value = evaluate_rule_status(rule, data)
                        state_key = (rule['target_gh'], rule['metric_name'])
                        previous_state = state_map.get(state_key)
                        is_active = int(previous_state['is_active']) == 1 if previous_state else False
                        last_alert_time = previous_state.get('last_alert_time') if previous_state else None

                        if status == "abnormal":
                            should_send = False
                            if not is_active:
                                should_send = True
                            elif last_alert_time and now - last_alert_time >= timedelta(hours=ALERT_COOLDOWN_HOURS):
                                should_send = True

                            if should_send:
                                reason = message if not is_active else f"持续异常提醒：{message}"
                                send_dingtalk_msg(rule['ding_webhook'], data, reason)

                            cursor.execute("""
                                INSERT INTO alert_state
                                    (target_gh, metric_name, is_active, last_status, last_alert_time, last_value)
                                VALUES (%s, %s, 1, 'abnormal', %s, %s)
                                ON DUPLICATE KEY UPDATE
                                    is_active = 1,
                                    last_status = 'abnormal',
                                    last_alert_time = IF(%s, %s, last_alert_time),
                                    last_value = %s
                            """, (
                                rule['target_gh'],
                                rule['metric_name'],
                                now if should_send else None,
                                str(current_value) if current_value is not None else data['value'],
                                1 if should_send else 0,
                                now,
                                str(current_value) if current_value is not None else data['value'],
                            ))
                            state_map[state_key] = {
                                'target_gh': rule['target_gh'],
                                'metric_name': rule['metric_name'],
                                'is_active': 1,
                                'last_alert_time': now if should_send else last_alert_time,
                            }
                        else:
                            if is_active:
                                send_recovery_msg(rule['ding_webhook'], data, message)
                            cursor.execute("""
                                INSERT INTO alert_state
                                    (target_gh, metric_name, is_active, last_status, last_recovery_time, last_value)
                                VALUES (%s, %s, 0, 'normal', %s, %s)
                                ON DUPLICATE KEY UPDATE
                                    is_active = 0,
                                    last_status = 'normal',
                                    last_recovery_time = %s,
                                    last_value = %s
                            """, (
                                rule['target_gh'],
                                rule['metric_name'],
                                now,
                                str(current_value) if current_value is not None else data['value'],
                                now,
                                str(current_value) if current_value is not None else data['value'],
                            ))
                            state_map[state_key] = {
                                'target_gh': rule['target_gh'],
                                'metric_name': rule['metric_name'],
                                'is_active': 0,
                                'last_alert_time': last_alert_time,
                            }
                except Exception:
                    continue
        conn.commit()
    except Exception as e:
        print(f"⚠️ 报警判定环节出错: {e}")
        conn.rollback()
    finally:
        conn.close()
if __name__ == "__main__":
    db_manager.init_db()
    run_single_sync()
    
    
