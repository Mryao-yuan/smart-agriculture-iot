
import streamlit as st
import plotly.graph_objects as go
import re
from datetime import datetime
from utils.iot_client import IotClient
from utils.text_operate import extract_gh_num
from utils.controllers import handle_toggle_change
from utils.timezone import get_local_now
from utils.weather import get_weather_amap
import db_manager
from config import *

def get_device_status_meta(device):
    if device.get('isDelete', 0) == 1:
        return "停用", "#94A3B8", "#334155"
    if device.get('isLine', 0) == 0:
        return "离线", "#FFA15A", "#7C2D12"
    if device.get('isAlarms', 0) == 1:
        return "报警", "#EF553B", "#7F1D1D"
    return "正常", "#00CC96", "#064E3B"

def sensor_display_value(sensor):
    sensor_type = sensor.get('sensorTypeId')
    if sensor_type in [2, 5, 6]:
        raw_state = str(sensor.get('switcher') if sensor.get('switcher') is not None else sensor.get('value', '0'))
        return "开启" if raw_state == "1" else "关闭"
    unit = sensor.get('unit') or ''
    raw_value = sensor.get('value', '--')
    try:
        value_num = float(raw_value)
        value_text = f"{value_num:.1f}".rstrip("0").rstrip(".")
    except Exception:
        value_text = str(raw_value)
    return f"{value_text} {unit}".strip()

def sensor_pretty_name(sensor_name):
    pretty_name = re.sub(r'^\d+[号组]', '', str(sensor_name or '')).strip()
    return pretty_name or str(sensor_name or "未知设备")

def sensor_accent_color(sensor):
    sensor_type = sensor.get('sensorTypeId')
    sensor_name = sensor_pretty_name(sensor.get("sensorName", "")).lower()
    if sensor_type in [2, 5, 6]:
        return "#16A34A" if sensor_display_value(sensor) == "开启" else "#94A3B8"
    if "温" in sensor_name:
        return "#F97316"
    if "湿" in sensor_name:
        return "#06B6D4"
    if "光" in sensor_name:
        return "#EAB308"
    if "ec" in sensor_name:
        return "#14B8A6"
    if "ph" in sensor_name:
        return "#8B5CF6"
    return "#334155"

def save_binding_work_order(record):
    finish_time = get_local_now().replace(microsecond=0)
    conn = db_manager.get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO work_orders (batch_id, gh_name, task_type, operator, content, duration_mins, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (*record, finish_time))
        conn.commit()
    finally:
        conn.close()

def render_greenhouse_selector_cards(devices):
    st.subheader("🗺️ 温室地图状态")
    st.caption("基于温室经纬度展示各棚状态，颜色对应正常/报警/离线/停用；下方可直接进入单棚设备沙盘。")
    sorted_devices = sorted(devices, key=lambda d: extract_gh_num(d.get('deviceName', '')))

    fig = go.Figure()
    status_groups = {}
    for device in sorted_devices:
        status_text, color, _ = get_device_status_meta(device)
        status_groups.setdefault(status_text, {"color": color, "devices": []})
        status_groups[status_text]["devices"].append(device)

    for status_text, group in status_groups.items():
        lats, lngs, texts, point_customdata = [], [], [], []
        for idx, device in enumerate(group["devices"]):
            try:
                base_lat = float(device.get('lat', 36.73291))
                base_lng = float(device.get('lng', 101.74776))
            except Exception:
                base_lat, base_lng = 36.73291, 101.74776
            offset_lat = base_lat + ((idx // 3) - 1) * 0.00012
            offset_lng = base_lng + ((idx % 3) - 1) * 0.00012
            lats.append(offset_lat)
            lngs.append(offset_lng)
            texts.append(
                f"<b>{device.get('deviceName', '未知温室')}</b><br>"
                f"状态：{status_text}<br>"
                f"在线：{'是' if device.get('isLine', 0) else '否'}<br>"
                f"报警：{'是' if device.get('isAlarms', 0) else '否'}<br>"
                f"节点数：{len(device.get('sensorsList') or [])}"
            )
            point_customdata.append([device.get('deviceName', '未知温室')])
        fig.add_trace(go.Scattermap(
            lat=lats,
            lon=lngs,
            mode='markers+text',
            text=[d.get('deviceName', '未知温室') for d in group["devices"]],
            textposition='top center',
            customdata=point_customdata,
            marker=dict(size=16, color=group["color"], opacity=0.95),
            name=status_text,
            hovertemplate="%{hovertext}<extra></extra>",
            textfont=dict(size=12, color='#0f172a'),
            hovertext=texts,
        ))

    center_lat = float(sorted_devices[0].get('lat', 36.73291))
    center_lng = float(sorted_devices[0].get('lng', 101.74776))
    fig.update_layout(
        map_style="open-street-map",
        map=dict(center=dict(lat=center_lat, lon=center_lng), zoom=12),
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        height=460,
        legend=dict(
            yanchor="top",
            y=0.98,
            xanchor="left",
            x=0.02,
            bgcolor="rgba(255, 255, 255, 0.92)",
            bordercolor="#CBD5E1",
            borderwidth=1,
        ),
    )
    st.plotly_chart(
        fig,
        use_container_width=True,
        key="greenhouse_status_map",
    )

    st.markdown("#### 进入设备沙盘")
    card_cols = st.columns(3, gap='large')
    for idx, device in enumerate(sorted_devices):
        status_text, color, text_color = get_device_status_meta(device)
        current_selected = st.session_state.get("selected_greenhouse") == device.get('deviceName')
        with card_cols[idx % 3]:
            st.markdown(
                f"""
                <div style="
                    border: 2px solid {color};
                    border-radius: 18px;
                    padding: 16px 18px;
                    background: linear-gradient(160deg, rgba(255,255,255,0.96), rgba(240,247,244,0.92));
                    box-shadow: 0 16px 30px rgba(15,23,42,0.08);
                    min-height: 132px;
                ">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                        <div style="font-size:20px; font-weight:700; color:#0f172a;">{device.get('deviceName', '未知温室')}</div>
                        <div style="padding:4px 10px; border-radius:999px; background:{color}; color:white; font-size:12px; font-weight:700;">{status_text}</div>
                    </div>
                    <div style="font-size:14px; color:#475569; line-height:1.7;">
                        在线状态：<span style="color:{text_color}; font-weight:700;">{'在线' if device.get('isLine', 0) else '离线'}</span><br>
                        报警标记：<span style="color:{text_color}; font-weight:700;">{'有报警' if device.get('isAlarms', 0) else '无报警'}</span><br>
                        数据节点：<span style="color:#0f172a; font-weight:700;">{len(device.get('sensorsList') or [])}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            btn_label = "✅ 当前查看中" if current_selected else f"进入 {device.get('deviceName', '温室')} 沙盘"
            if st.button(btn_label, key=f"select_gh_card_{device.get('deviceNo', idx)}", use_container_width=True):
                st.session_state["selected_greenhouse"] = device.get('deviceName')
                st.session_state["selected_sandbox_sensor"] = None
                st.session_state["menu_target"] = "🎮 单棚设备沙盘"
                st.rerun()

@st.cache_data(ttl=900, show_spinner=False)
def get_cached_weather(lat, lng, api_key):
    return get_weather_amap(lat, lng, api_key)

def render_binding_form(active_batch_labels, batch_lookup):
    pending = st.session_state.get("pending_control_binding")
    if not pending:
        return
    st.divider()
    st.subheader("📝 控制动作联动农事记录")
    if pending["form_type"] == "cooling_humidify":
        st.info(
            f"系统检测到【{pending['gh_name']}】的【{pending['sensor_name']}】发生{pending['action_text']}动作。"
            "请补充降温/加湿作业记录。"
        )
        default_task = "💧 智能灌溉"
        placeholder = "例如：高温时段开启雾化 1 次，用于快速降温增湿。"
    else:
        st.info(
            f"系统检测到【{pending['gh_name']}】的【{pending['sensor_name']}】发生{pending['action_text']}动作。"
            "请补充通风/保温作业记录。"
        )
        default_task = "🌀 强制通风"
        placeholder = "例如：午间升温较快，开启侧卷膜进行通风换气。"

    matched_batch_labels = [label for label in active_batch_labels if batch_lookup[label]["gh_name"] == pending["gh_name"]]
    with st.form("pending_control_binding_form"):
        f1, f2 = st.columns([2, 1])
        if matched_batch_labels:
            selected_batch_label = f1.selectbox("关联批次", matched_batch_labels, key="binding_batch")
        else:
            selected_batch_label = f1.selectbox("关联批次", ["无运行中批次"], disabled=True, key="binding_batch_disabled")
        operator = f2.text_input("执行负责人", value="系统联动", key="binding_operator")
        content = st.text_area(
            "作业记录",
            value=(
                f"动作时间：{pending['event_time']}\n"
                f"目标温室：{pending['gh_name']}\n"
                f"控制对象：{pending['sensor_name']}\n"
                f"执行动作：{pending['action_text']}\n"
            ),
            placeholder=placeholder,
            key="binding_content"
        )
        submitted = st.form_submit_button("💾 生成联动工单", type="primary", use_container_width=True)
        cancel = st.form_submit_button("关闭此表单", use_container_width=True)
        if cancel:
            st.session_state["pending_control_binding"] = None
            st.rerun()
        if submitted:
            if not matched_batch_labels:
                st.warning("当前温室没有运行中的批次，无法归档联动工单。")
            elif not operator.strip():
                st.warning("请填写执行负责人。")
            elif not content.strip():
                st.warning("请填写作业记录。")
            else:
                selected_batch = batch_lookup[selected_batch_label]
                save_binding_work_order((
                    selected_batch["batch_id"],
                    selected_batch["gh_name"],
                    default_task,
                    operator.strip(),
                    content.strip(),
                    None,
                ))
                st.success("联动工单已归档。")
                st.session_state["pending_control_binding"] = None
                st.rerun()

def render_greenhouse_sandbox(target_device):
    st.subheader(f"🧪 单棚设备沙盘：{target_device.get('deviceName', '未知温室')}")
    st.caption("按温室布局查看设备位置，点击设备卡片可查看实时数据；控制类设备支持直接操作。")
    sensors_list = target_device.get("sensorsList", []) or []
    device_no = target_device.get("deviceNo")
    is_online = target_device.get('isLine', False)
    status_text, status_color, _ = get_device_status_meta(target_device)

    info_cols = st.columns(4)
    info_cols[0].metric("温室状态", status_text)
    info_cols[1].metric("在线节点", f"{sum(1 for s in sensors_list if str(s.get('isLine', 1)) == '1')} 个")
    info_cols[2].metric("控制节点", f"{sum(1 for s in sensors_list if s.get('sensorTypeId') in [2, 5, 6])} 个")
    info_cols[3].metric("监测节点", f"{sum(1 for s in sensors_list if s.get('sensorTypeId') == 1)} 个")
    st.markdown(
        f"<div style='height:8px; border-radius:999px; background:{status_color}; margin: 4px 0 18px;'></div>",
        unsafe_allow_html=True
    )
    def classify_sensor(sensor):
        name = sensor.get("sensorName", "")
        sensor_type = sensor.get("sensorTypeId")
        if sensor_type in [2, 5, 6]:
            if any(k in name for k in ["卷膜", "卷被", "侧卷", "顶窗"]):
                return "roof"
            if any(k in name for k in ["雾化", "喷淋", "喷灌", "水泵"]):
                return "middle"
            return "side"
        if any(k in name for k in ["土壤", "地温", "PH", "EC"]):
            return "ground"
        if any(k in name for k in ["光", "辐射"]):
            return "roof"
        return "middle"

    layout_groups = {
        "roof": [],
        "middle": [],
        "ground": [],
        "side": [],
    }
    for sensor in sensors_list:
        layout_groups[classify_sensor(sensor)].append(sensor)

    def get_sensor_zone(sensor):
        name = sensor.get("sensorName", "")
        sensor_type = sensor.get("sensorTypeId")
        if sensor_type in [2, 5, 6]:
            if any(k in name for k in ["卷膜", "卷被", "侧卷", "顶窗"]):
                return "顶部棚膜"
            if any(k in name for k in ["雾化", "喷淋", "喷灌", "水泵"]):
                return "中部控制"
            return "侧边控制"
        if any(k in name for k in ["土壤", "地温", "PH", "EC"]):
            return "地面根区"
        if any(k in name for k in ["光", "辐射"]):
            return "顶部感知"
        return "中部感知"

    panel_cols = st.columns([1.6, 1], gap="large")
    with panel_cols[0]:
        st.markdown("#### 🗺️ 温室数字孪生分布图")

        def get_sensor_ui(sensor):
            name = sensor.get("sensorName", "")
            type_id = sensor.get("sensorTypeId")

            if type_id in [2, 5, 6]:
                if any(k in name for k in ["卷膜", "卷被", "顶窗"]): return "⚙️", "#475569"
                if any(k in name for k in ["泵", "阀", "雾化"]): return "🚰", "#0284C7"
                if "灯" in name or "补光" in name: return "💡", "#D97706"
                if "暖风" in name or "加热" in name: return "♨️", "#EF4444"
                return "🔌", "#475569"
            
            # 环境监测类设备
            if "温" in name and "土壤" not in name and "地" not in name: return "🌡️", "#DC2626"
            if "湿" in name and "土壤" not in name: return "💧", "#2563EB"
            if "CO2" in name or "二氧化碳" in name: return "☁️", "#0D9488"
            if "光" in name or "辐射" in name: return "☀️", "#D97706"
            
            # 土壤与根区监测
            if any(k in name for k in ["土壤", "地温", "EC", "PH", "ph"]):
                if "温" in name: return "🌱", "#65A30D"
                if "湿" in name: return "💦", "#0891B2"
                if "PH" in name.upper() or "EC" in name.upper(): return "🧪", "#7C3AED"
                return "🪨", "#854D0E"
                
            return "📡", "#475569"

        # ================= 🌟 2. 高密度防重叠网格算法 (扩大根区 & 集中侧边) =================
        def distribute_coords(group_key, count):
            xs, ys = [], []
            if count == 0: return xs, ys

            # 将暖风、补光灯等辅助设备全部集中在右侧一列
            if group_key == "side":
                for i in range(count):
                    xs.append(0.93) # 固定在右侧边缘
                    ys.append(0.80 - i * 0.12) # 自上而下整齐排列
                return xs, ys

            # 动态网格：重新分配Y轴空间，给根区(ground)留出极大空间
            y_base = {"roof": 0.89, "middle": 0.65, "ground": 0.38}[group_key] 
            cols = 6 if group_key == "ground" else 5  # 根区一排最多放6个
            y_step = 0.1 if group_key == "ground" else 0.12
            
            for i in range(count):
                row = i // cols
                col = i % cols
                current_row_count = cols if i < (count - count % cols) else count % cols
                
                # 将主设备区稍微向左挤一点 (0.10~0.82)，给右侧的侧边控制设备留出专属走廊
                x_val = 0.46 if current_row_count == 1 else 0.10 + (0.72 / (current_row_count - 1)) * col
                xs.append(x_val)
                ys.append(y_base - (row * y_step))
            return xs, ys

        # ================= 🌟 3. 构建高颜值背景基座 (重新划定比例) =================
        fig_layout = go.Figure()
        
        # 外层大虚线框
        fig_layout.add_shape(type="rect", x0=0.03, y0=0.01, x1=0.97, y1=0.99, 
                             line=dict(color="#0F766E", width=3, dash="dot"), fillcolor="rgba(240,253,250,0.4)")
        
        # 顶部区块 (变窄)
        fig_layout.add_shape(type="rect", x0=0.06, y0=0.76, x1=0.86, y1=0.96, line_width=0, fillcolor="rgba(224, 242, 254, 0.3)")
        fig_layout.add_annotation(x=0.46, y=0.94, text="⬆️ 顶部气象与棚膜控制区", showarrow=False, font=dict(size=12, color="#0284C7"))
        
        # 中部区块 (变窄)
        fig_layout.add_shape(type="rect", x0=0.06, y0=0.46, x1=0.86, y1=0.74, line_width=0, fillcolor="rgba(204, 251, 246, 0.3)")
        fig_layout.add_annotation(x=0.46, y=0.72, text="🎛️ 中部环境感知与调控区", showarrow=False, font=dict(size=12, color="#0F766E"))
        
        # 底部根区 (大幅度拉高，占据约40%空间)
        fig_layout.add_shape(type="rect", x0=0.06, y0=0.03, x1=0.86, y1=0.44, line_width=0, fillcolor="rgba(236, 252, 203, 0.3)")
        fig_layout.add_annotation(x=0.46, y=0.46, text="🌱 根区水肥与土壤感知区", showarrow=False, font=dict(size=12, color="#4D7C0F"))

        # ================= 🌟 4. 渲染设备节点 (极简纯净模式) =================
        for zone_key, sensors in layout_groups.items():
            count = len(sensors)
            if count == 0: continue
            
            xs, ys = distribute_coords(zone_key, count)
            
            for i, sensor in enumerate(sensors):
                x_val, y_val = xs[i], ys[i]
                icon, main_color = get_sensor_ui(sensor)
                
                name = str(sensor.get("sensorName", "未知"))
                val_text = sensor_display_value(sensor)
                sensor_id = sensor.get("id")
                
                # 纯净换行悬浮窗
                hover_html = (
                    f"<b style='font-size:14px; color:{main_color}'>{icon} {name}</b><br><br>"
                    f"实时状态：<b>{val_text}</b><br>"
                    f"数据上报：{sensor.get('updateDate', '未知')}<br>"
                    f"<i>* 点击固定至右侧面板控制</i>"
                )

                customdata = [[sensor_id, device_no]]

                display_label = f"{icon}<br><span style='font-size:11px; color:#475569'>{name}</span>"
                
                fig_layout.add_trace(go.Scatter(
                    x=[x_val], y=[y_val],
                    mode="text",
                    text=[display_label],
                    textposition="middle center",
                    textfont=dict(size=26), # 图标尺寸稍微调大
                    customdata=customdata,
                    hovertemplate=hover_html + "<extra></extra>",
                    showlegend=False,
                    hoverlabel=dict(bgcolor="white", font_size=13, bordercolor=main_color)
                ))

        # ================= 🌟 5. 面板全局参数调优 (整体拉高) =================
        fig_layout.update_layout(
            height=750, # 🌟 核心：画板总高度从 580 提升至 750
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(visible=False, range=[0, 1]),
            yaxis=dict(visible=False, range=[0, 1]),
            plot_bgcolor="rgba(255,255,255,1)",
            paper_bgcolor="rgba(255,255,255,0)",
            dragmode=False 
        )

        sandbox_event = st.plotly_chart(
            fig_layout,
            use_container_width=True,
            key=f"greenhouse_sandbox_{device_no}",
            on_select="rerun",
            selection_mode="points",
        )
        
        sandbox_selected_points = (sandbox_event or {}).get("selection", {}).get("points", []) if isinstance(sandbox_event, dict) else []
        if sandbox_selected_points:
            selected_data = sandbox_selected_points[0].get("customdata", [])
            if len(selected_data) >= 2:
                current_ctx = st.session_state.get("selected_sandbox_sensor") or {}
                if current_ctx.get("device_no") != selected_data[1] or current_ctx.get("sensor_id") != selected_data[0]:
                    st.session_state["selected_sandbox_sensor"] = {
                        "device_no": selected_data[1],
                        "sensor_id": selected_data[0],
                    }

        st.info("💡 **操作指引**：点击沙盘图上的气泡节点，右侧面板将同步切换至该设备的实控详情。")
    

    
    with panel_cols[1]:
        selected_sensor_ctx = st.session_state.get("selected_sandbox_sensor") or {}
        selected_sensor_id = selected_sensor_ctx.get("sensor_id")
        selected_device_no = selected_sensor_ctx.get("device_no")
        default_sensor = sensors_list[0] if sensors_list else None
        if selected_device_no != device_no and default_sensor:
            selected_sensor = default_sensor
        else:
            selected_sensor = next((sensor for sensor in sensors_list if sensor.get("id") == selected_sensor_id), default_sensor)

        if not selected_sensor:
            st.info("当前温室没有可展示的设备节点。")
            return

        st.markdown("#### 设备详情")
        s_name = selected_sensor.get("sensorName", "未知设备")
        s_time = selected_sensor.get("updateDate", "未知时间")
        s_id = selected_sensor.get("id", "未知ID")
        s_type = selected_sensor.get("sensorTypeId")
        st.markdown(
            f"""
            <div style="border-radius:22px; padding:18px; background:linear-gradient(160deg, rgba(255,255,255,0.95), rgba(248,250,252,0.92)); border:1px solid rgba(148,163,184,0.2); box-shadow:0 20px 40px rgba(15,23,42,0.08);">
                <div style="font-size:20px; font-weight:700; color:#0f172a; margin-bottom:8px;">{s_name}</div>
                <div style="font-size:14px; color:#475569; line-height:1.8;">
                    传感器ID：<b>{s_id}</b><br>
                    更新时间：<b>{s_time}</b><br>
                    当前数值：<b>{sensor_display_value(selected_sensor)}</b>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if s_type in [2, 5, 6]:
            st.markdown("#### 控制面板")
            if st.session_state.get("api_client") is None:
                client = IotClient()
                login_res = client.login(USERNAME, PASSWORD, API_KEY)
                if login_res.get("flag") == "00":
                    token_res = client.get_access_token(USERNAME, PASSWORD)
                    if token_res.get("flag") == "00":
                        st.session_state["api_client"] = client
            client = st.session_state.get("api_client")
            current_state = str(selected_sensor.get("switcher") if selected_sensor.get("switcher") is not None else selected_sensor.get("value", "0")) == "1"
            toggle_key = f"sandbox_ctrl_toggle_{device_no}_{s_id}"
            st.toggle(
                label=f"控制 {s_name}",
                value=current_state,
                key=toggle_key,
                disabled=not is_online,
                on_change=handle_toggle_change,
                args=(client, target_device.get("deviceName"), device_no, s_id, s_name, selected_sensor, toggle_key),
            )
            st.caption("控制动作会自动进入农事联动记录流程。")
        else:
            st.markdown("#### 实时监测")
            st.metric("当前读数", sensor_display_value(selected_sensor))
            st.caption("点击左侧其他设备卡片，可切换查看不同节点实时数据。")
