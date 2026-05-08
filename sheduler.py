import time
from iot_client import IotClient
import streamlit as st
from database_manager import sync_iot_nested_data
from utils import data_process,convert_device_data
from config import *

def start_scheduler():
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
    print("✅ 获取访问令牌成功！")
    last_refresh_time = time.time()
    while True:
        try:
            # ================= 1. 定时刷新token（每50分钟） =================
            if time.time() - last_refresh_time > 30 * 60:
                print("🔄 刷新Token...")
                refresh_res = client.refresh_token()
                if refresh_res.get("flag") != "00":
                    print("⚠️ refresh失败，重新登录...")
                    client.login(USERNAME, PASSWORD, API_KEY)
                    client.get_access_token(USERNAME, PASSWORD)
                else:
                    print("✅ Token刷新成功")
                last_refresh_time = time.time()
            # ================= 2. 拉数据 =================
            data = client.get_devices_sensor_datas()
            if data.get("flag") != "00":
                print("⚠️ API返回异常，尝试刷新token")
                # 尝试刷新
                refresh_res = client.refresh_token()
                if refresh_res.get("flag") != "00":
                    print("❌ refresh失败，重新登录")
                    client.login(USERNAME, PASSWORD, API_KEY)
                    client.get_access_token(USERNAME, PASSWORD)
                continue
            sync_iot_nested_data(data)
            print("✅ 数据同步完成")
        except Exception as e:
            print("❌ 同步异常:", e)
        time.sleep(SYNC_INTERVAL)

@st.cache_data(ttl=300)
def device_info_get():
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
    print("✅ 获取访问令牌成功！")
    data_res = client.get_devices_sensor_datas()
    return data_res
    # try:
    #         # devices_data,sensors_data = data_process(data_res)
    #         # print("✅ 设备数据处理完成！")
    #         # print("设备列表:", devices_data)
    #         # print("传感器列表:", sensors_data)
    #         # return devices_data,sensors_data
    # except Exception as e:
    #     print("❌ 同步异常:", e)
        
        
        


if __name__ == "__main__":
    start_scheduler()

# 上述运行出现“2026-05-08 00:26:18.519 WARNING streamlit.runtime.caching.cache_data_api: No runtime found, using MemoryCacheStorageManager”
# 什么意思