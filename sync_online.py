import requests
import pymysql
import json
from datetime import datetime
import re
import db_manager
from config import *
from utils.iot_client import IotClient  


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
            if not rules: return
            for data in snapshot:
                    try:
                        s_type = data.get('sensor_type')
                        if s_type == 1:
                            base_name = re.sub(r'^\d+[号组]', '', data['sensor_name']).strip()
                        else:
                            base_name = data['sensor_name']
                        for rule in rules:
                            if rule['target_gh'] == data['device_name'] and rule['metric_name'] == base_name:
                                val = float(data['value'])
                                reason = ""
                                if s_type == 1:
                                    if val > rule['max_val']:
                                        reason = f"数值超过上限 {rule['max_val']}"
                                    elif val < rule['min_val']:
                                        reason = f"数值低于下限 {rule['min_val']}"
                                elif s_type ==  2:
                                    if val == rule['max_val']:
                                        # 给人看的友好提示：如果值为 1 提示触发/异常，为 0 提示关闭/恢复
                                        state_desc = "触发/异常/开启" if val == 1.0 else "正常/关闭"
                                        reason = f"设备状态变为设定目标: {int(val)} ({state_desc})"
                                if reason:
                                    send_dingtalk_msg(rule['ding_webhook'], data, reason)
                    except: continue
    except Exception as e:
        print(f"⚠️ 报警判定环节出错: {e}")
    finally:
        conn.close()
if __name__ == "__main__":
    db_manager.init_db()
    run_single_sync()
    
    

