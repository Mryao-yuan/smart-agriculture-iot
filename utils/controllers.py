import streamlit as st

DEBUG_MODE = True

def handle_toggle_change(client, d_name,d_no, s_id, s_name,sensor_dict,toggle_key):
    """
    处理开关设备状态改变的回调函数
    """
    new_state = st.session_state[toggle_key]
    target_switcher = 1 if new_state else 0

    # 乐观更新本地数据，防止闪烁
    sensor_dict["switcher"] = str(target_switcher)
    sensor_dict["value"] = str(target_switcher)
    
    if DEBUG_MODE:
        # 在前端弹出提示，让你知道逻辑进来了
        st.toast(f"[测试模式拦截] 准备向【{s_name}】下发 {'开启' if target_switcher == 1 else '关闭'} 指令 (ID: {s_id})", icon="🛡️")
        # 在后台终端打印参数，让你核对传参对不对
        print(f"✅ [DEBUG] 成功捕获控制事件！\n参数检查：")
        print(f"   - 目标设备: {d_name}")
        print(f"   - 目标设备: {d_no}")
        print(f"   - 传感器: {s_name}")
        print(f"   - 传感器ID: {s_id}")
        print(f"   - 下发动作: {target_switcher} (0关1开)")
        print(f"   - Client是否就绪: {'是' if client else '否'}")
        return 
    try:
        res = client.switcher_controller(
            device_no=d_no, 
            sensor_id=s_id, 
            switcher=target_switcher
        )
        if res:
            st.toast(f"✅ 已向【{s_name}】下发 {'开启' if target_switcher == 1 else '关闭'} 指令！", icon="🚀")
        else:
            st.toast(f"⚠️ 【{s_name}】指令下发可能失败，请检查网络。", icon="⚠️")
    except Exception as e:
        st.toast(f"❌ 接口报错: {e}", icon="❌")