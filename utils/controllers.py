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



def execute_batch_control(client, target_ghs, target_sensor_name, target_switcher_val):
    """
    执行批量设备控制的封装函数
    
    参数:
        client: IotClient 实例 (测试模式下可为 None)
        target_ghs: list, 目标大棚名称列表
        target_sensor_name: str, 目标设备名称 (如 "1号卷膜")
        target_switcher_val: int, 目标状态 (1 开, 0 关)
        
    返回:
        tuple: (成功数, 失败数, 跳过数, 执行明细列表)
    """
    success_count = 0
    fail_count = 0
    skip_count = 0
    exec_details = [] 

    for d in st.session_state.device_data:
        gh_name = d.get('deviceName')
        
        # 只处理勾选的大棚
        if gh_name in target_ghs:
            device_no = d.get('deviceNo')
            for s in d.get('sensorsList', []):
                s_type = s.get('sensorTypeId')
                
                # 确保是开关型设备
                if s_type in [2, 5, 6]:
                    current_name = s.get('sensorName', '').strip()
                    if current_name == target_sensor_name:
                        sensor_id = s.get('id')

                        current_is_on = (str(s.get("switcher")) == "1" or str(s.get("value")) == "1")
                        
                        if (target_switcher_val == 1 and current_is_on):
                            exec_details.append({
                                "大棚": gh_name, "对象": current_name, 
                                "动作": "开启", "执行结果": "⏭️ 物理设备已是开启状态，安全跳过"
                            })
                            skip_count += 1
                            continue 
                            
                        elif (target_switcher_val == 0 and not current_is_on):
                            exec_details.append({
                                "大棚": gh_name, "对象": current_name, 
                                "动作": "关闭", "执行结果": "⏭️ 物理设备已是关闭状态，安全跳过"
                            })
                            skip_count += 1
                            continue 

                        action_text = "开启" if target_switcher_val else "关闭 🔴"
                        
                        if DEBUG_MODE:
                            print(f"✅ [DEBUG 批处理] 模拟向 {gh_name}的{current_name}(ID:{sensor_id}) 下发 {action_text}")
                            exec_details.append({
                                "大棚": gh_name, "对象": current_name, 
                                "动作": action_text, "执行结果": "🛡️ 模拟指令发送成功 (未篡改本地状态)"
                            })
                            success_count += 1
                            
                        else:
                            try:
                                ctrl_res = client.switcher_controller(
                                    device_no=device_no, sensor_id=sensor_id, switcher=target_switcher_val
                                )
                                if ctrl_res: 
                                    s["switcher"] = str(target_switcher_val)
                                    s["value"] = str(target_switcher_val)
                                    
                                    exec_details.append({
                                        "大棚": gh_name, "对象": current_name, 
                                        "动作": action_text, "执行结果": "✅ 真实触达并同步状态"
                                    })
                                    success_count += 1
                                else:
                                    exec_details.append({
                                        "大棚": gh_name, "对象": current_name, 
                                        "动作": action_text, "执行结果": "❌ 硬件响应异常"
                                    })
                                    fail_count += 1
                            except Exception as e:
                                exec_details.append({
                                    "大棚": gh_name, "对象": current_name, 
                                    "动作": action_text, "执行结果": f"⚠️ API请求失败"
                                })
                                fail_count += 1
                                
    return success_count, fail_count, skip_count, exec_details