import db_manager
from config import *
from iot_client import IotClient  # 请确保导入路径和你的实际代码一致

def run_single_sync():
    print("🚀 [云端调度] 开始执行单次 IoT 数据同步...")
    
    # 初始化你的 IoT 客户端
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
    data = client.get_devices_sensor_datas()
    if data:
        db_manager.sync_iot_nested_data(data)
        print("✅ [云端调度] 单次同步入库完成！")
    else:
        print("⚠️ [云端调度] 未获取到有效数据。")

if __name__ == "__main__":
    db_manager.init_db()
    run_single_sync()