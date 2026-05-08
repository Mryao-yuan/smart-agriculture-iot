import db_manager
from iot_client import IotClient  # 请确保导入路径和你的实际代码一致

def run_single_sync():
    print("🚀 [云端调度] 开始执行单次 IoT 数据同步...")
    
    # 初始化你的 IoT 客户端
    client = IotClient()

    success, data = client.get_devices_sensor_datas()
    
    if success and data:
        # 存入 TiDB 数据库
        db_manager.sync_iot_nested_data(data)
        print("✅ [云端调度] 单次同步入库完成！")
    else:
        print("⚠️ [云端调度] 未获取到有效数据。")

if __name__ == "__main__":
    db_manager.init_db()
    run_single_sync()