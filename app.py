import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import re
from datetime import datetime, timedelta
import plotly.express as px
from datetime import datetime, timedelta
import plotly.graph_objects as got

from sheduler import device_info_get
from config import *
import database_manager 
import db_manager


from utils.weather import get_weather_amap,init_weather_alert_config,get_weather_alert
from utils.login import check_password
from utils.text_operate import extract_gh_num,get_sorted_devices,parse_zone,process_history_records
from utils.alter import user_webhook_check
from utils.style import load_local_css,generate_sensor_card_html
from utils.controllers import handle_toggle_change, execute_batch_control
from utils.iot_client import IotClient
from datetime import datetime



bg_path = "imgs/bg1.png"
json_path="./users.json"


# === login ===
# if not check_password(bg_path,json_path):
#     st.stop()

# ==================== 1. 基础配置与全局工具 ====================
st.set_page_config(page_title="智慧温室 IoT 平台", layout="wide", page_icon="🌿")

# ==================== 2. Session 状态初始化 ====================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'device_data' not in st.session_state:
    st.session_state.device_data = [] # 存放拉取的真实设备数据

# ==================== 3. 侧边栏导航 ====================
with st.sidebar:
    st.title("🌿 智慧温室 IoT 平台")
    # 页面路由菜单
    menu = st.radio("🏠 业务导航", [
        "🌐 设备整体状态", 
        # "🎮 单棚孪生与控制 (管细节)", 
        "📈 多维数据分析 (查根因)", 
        "📋 批次工单与联控 (抓生产)",
        "⚙️ 策略与预警 (设规则)"
    ])

    data = device_info_get() 
    st.session_state.device_data = data.get("dataList", [])

    if st.button("退出登录"):
        st.session_state.logged_in = False
        st.rerun()

# if not st.session_state.device_data:
#     st.warning("👈 请点击左侧【同步云端最新数据】拉取平台台账。")

# ==================== 4. 核心业务页面 ====================

# ----------------- 页面一：全局驾驶舱 -----------------
if menu == "🌐 设备整体状态":
    st.header("设备情况")
    init_weather_alert_config()
    config = st.session_state.weather_alert_config
    # 获取天气信息
    if st.session_state.device_data:
        first_device = st.session_state.device_data[0]
        lat = first_device.get('lat')
        lng = first_device.get('lng')
        
        weather_info = get_weather_amap(lat, lng, WEATHER_API_KEY)
        if weather_info:
            # 1. 获取预警结果
            alert_level, alert_msg = get_weather_alert(weather_info, config)
            # 2. 拼接横幅文本
            city = weather_info.get('location', '未知地区').split('省')[-1] # 简化名字
            weather = weather_info.get('weather', '未知')
            temp = weather_info.get('temperature', '--')
            humidity = weather_info.get('humidity', '--')
            wind_power = weather_info.get('wind_power', '--')
            # 基础文本
            banner_text = f"🌤️ {city} 当前天气：{weather} | 温度 {temp}℃ 湿度 {humidity}% 风力 {wind_power}级"
            # 3. 动态渲染横幅 (根据预警级别变色)
            if alert_level == "error":
                st.error(f"{banner_text} | 🚨 **报警**：{alert_msg}")
            elif alert_level == "warning":
                st.warning(f"{banner_text} | ⚠️ **注意**：{alert_msg}")
            else:
                st.info(f"{banner_text} | ✅ 暂无天气预警信息")

    # ==================== 可折叠的天气预警设置 ====================
    with st.expander("⚙️ 天气预警参数设置 (点击展开/收起)", expanded=False):
        with st.form("weather_alert_form"):
            st.caption("调整阈值后点击保存，上方天气横幅将实时刷新预警状态。")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("#### 🌡️ 温度预警")
                new_temp_high = st.number_input("高温预警阈值 (℃)", min_value=20, max_value=50, value=config['temp_high'])
                new_temp_low = st.number_input("低温预警阈值 (℃)", min_value=-20, max_value=20, value=config['temp_low'])
                
                st.markdown("#### 💨 风力预警")
                new_wind = st.number_input("大风预警阈值 (级)", min_value=1, max_value=12, value=config['wind_power'])
                
            with col2:
                st.markdown("#### 💧 湿度预警")
                new_hum_high = st.number_input("高湿预警阈值 (%)", min_value=50, max_value=100, value=config['humidity_high'])
                new_hum_low = st.number_input("低湿预警阈值 (%)", min_value=0, max_value=50, value=config['humidity_low'])
                
                st.markdown("#### 🔔 预警开关")
                # st.form 中不支持 toggle，所以用 checkbox 替代
                new_enable = st.checkbox("启用天气预警", value=config['enable_alerts'])

            # 提交按钮
            submit_btn = st.form_submit_button("💾 保存配置", type="primary", width = 'stretch')
            
            if submit_btn:
                # 将用户输入的新值覆盖到 session_state 中
                st.session_state.weather_alert_config.update({
                    'temp_high': new_temp_high,
                    'temp_low': new_temp_low,
                    'wind_power': new_wind,
                    'humidity_high': new_hum_high,
                    'humidity_low': new_hum_low,
                    'enable_alerts': new_enable
                })
                # 提示成功并刷新页面以更新上方横幅
                st.toast("✅ 天气预警规则已保存！")
                st.rerun()
    st.subheader("设备地图状态")
    if st.session_state.device_data:
        # 1. 提前统计三种状态的数量
        normal_cnt = sum(1 for d in st.session_state.device_data if d.get('isLine', 0) != 0 and d.get('isAlarms', 0) == 0)
        offline_cnt = sum(1 for d in st.session_state.device_data if d.get('isLine', 0) == 0)
        alarm_cnt = sum(1 for d in st.session_state.device_data if d.get('isLine', 0) != 0 and d.get('isAlarms', 0) == 1)

        fig = go.Figure()

        status_configs = [
            {"name": f"正常 ({normal_cnt})", "color": "#00CC96", "condition": lambda d: d.get('isLine',0) != 0 and d.get('isAlarms',0) == 0},
            {"name": f"报警 ({alarm_cnt})", "color": "#EF553B", "condition": lambda d: d.get('isLine',0) != 0 and d.get('isAlarms',0) == 1},
            {"name": f"离线 ({offline_cnt})", "color": "#FFA15A", "condition": lambda d: d.get('isLine',0) == 0}
        ]
        # 4. 遍历配置，分别添加图层 (Trace)
        for config in status_configs:
            lats = []
            lngs = []
            texts = []
            
            for idx, d in enumerate(st.session_state.device_data):
                if config["condition"](d):
                    base_lat = float(d.get('lat', 36.73291))
                    base_lng = float(d.get('lng', 101.74776))
                    # 微小网格偏移（防止坐标完全相同导致重叠）
                    offset_lat = base_lat + ((idx // 3) - 1) * 0.00015  
                    offset_lng = base_lng + ((idx % 3) - 1) * 0.00015
                    
                    lats.append(offset_lat)
                    lngs.append(offset_lng)
                    
                    # 自定义鼠标悬浮提示的文本
                    status_str = config['name'].split(' ')[0]
                    texts.append(f"<b>{d.get('deviceName', f'设备{idx}')}</b><br>状态: {status_str}")
            fig.add_trace(go.Scattermap(
                lat=lats,
                lon=lngs,
                mode='markers',
                marker=dict(size=14, color=config["color"]), # 这里直接用 dict 写法更简洁，不易报错
                name=config["name"], 
                hoverinfo="text",
                text=texts,
                showlegend=True 
            ))
        # 5. 获取地图初始中心点
        center_lat = float(st.session_state.device_data[0].get('lat', 36.73291))
        center_lng = float(st.session_state.device_data[0].get('lng', 101.74776))

        # 6. 配置地图底图和图例位置
        fig.update_layout(
            map_style="open-street-map",
            map=dict(
                center=dict(lat=center_lat, lon=center_lng),
                zoom=12
            ),
            margin={"r":0,"t":0,"l":0,"b":0},
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.98,
                xanchor="left",
                x=0.02,
                bgcolor="rgba(255, 255, 255, 0.9)", # 白色半透明背景，防止与地图重叠看不清
                bordercolor="#ccc",
                borderwidth=1,
                font=dict(size=14, color="#333")
            ),
            height=400
        )
        
        st.plotly_chart(fig, width = 'stretch')

    else:
        st.info("暂无设备坐标数据")

    # ==================== 【需求2】联动查看单设备传感器详情 ====================
    st.subheader("🔍 设备传感器详细看板")
    st.caption("选择大棚，查看其挂载的所有实时传感器数据。")
    
    device_names = [d['deviceName'] for d in st.session_state.device_data]
    sorted_device_names = sorted(device_names, key=extract_gh_num)
    
    col_1, col_2 = st.columns(2)
    with col_1:
        selected_gh = st.selectbox("🏠 选择要查看的大棚", sorted_device_names)
    with col_2:
        # 数值类型 1 开关类型 2
        selected_type_label = st.selectbox("🔍 选择传感器类型", ["数值","开关"])
        
    selected_type_flag = 1 if selected_type_label == "数值" else 2
    
    target_device = next(d for d in st.session_state.device_data if d['deviceName'] == selected_gh)
    sensors_list = target_device.get("sensorsList", [])
    device_no = target_device.get("deviceNo")
    is_online = target_device.get('isLine', False) # 设备是否在线
    
    if not sensors_list:
        st.info(f"暂未获取到 {selected_gh} 的传感器数据 (sensorsList 为 null)。")
    else:
        env_sensors = [s for s in sensors_list if s.get('sensorTypeId') == selected_type_flag and \
            (s.get('sensorTypeId') != 1 or s.get("value") not in ['0', '0.0', ]
    )]
        
        if env_sensors:
            load_local_css("assets/style.css")
            if selected_type_flag  == 2: 
                cols = st.columns(3)
                if st.session_state.get("api_client") is None:
                    client = IotClient()
                    login_res = client.login(USERNAME, PASSWORD, API_KEY)
                    print("🔐 正在登录...")
                    if login_res.get("flag") != "00":
                        print("❌ 登录失败:")
                    else:
                        token_res = client.get_access_token(USERNAME, PASSWORD)
                        if token_res.get("flag") != "00":
                            print("❌ 获取访问令牌失败:")
                        else:
                            print("✅ 获取访问令牌成功！可以下发控制指令了！")
                            st.session_state["api_client"] = client
                client = st.session_state.get("api_client")
                for idx, sensor in enumerate(env_sensors):
                    s_name = sensor.get("sensorName", "未知")
                    sensor_id = sensor.get("id")
                    s_time = sensor.get("updateDate", "未知时间")
                    is_on = str(sensor.get("switcher")) == "1" or str(sensor.get("value")) == "1"
                    with cols[idx % 3]:
                        with st.container(border=True):
                            toggle_key = f"ctrl_toggle_{device_no}_{sensor_id}"
                            
                            st.toggle(
                                label=s_name,  
                                value=is_on,         # 当前开关滑块的位置
                                key=toggle_key, # 确保页面 key 唯一
                                disabled=not is_online, # 如果大棚整体掉线，直接禁用按钮防误触
                                on_change=handle_toggle_change, 
                                args=(client,target_device.get("deviceName"), device_no, sensor_id,  s_name,sensor,toggle_key)
                            )
                            st.caption(f"📅 ：{s_time}")
                            st.caption(f"ID：{sensor_id}")         
            else:
                # 只读卡片排 4 列
                cols = st.columns(4)
                # components.generate_sensor_card_html assumed available
                for idx, sensor in enumerate(env_sensors):
                    s_name = sensor.get("sensorName", "未知")
                    s_unit = sensor.get("unit", "")
                    s_time = sensor.get("updateDate", "未知时间")
                    s_id = sensor.get("id", "未知ID")
                    # 数值型显示
                    s_val = sensor.get("value", "--")
                    val_color_style = "color: #1f77b4;" # 默认蓝色数值颜色
                    
                    with cols[idx % 4]:
                        card_html = generate_sensor_card_html(s_name, val_color_style, s_val, s_unit, s_time, s_id)
                        st.markdown(card_html, unsafe_allow_html=True)
        else:
            mode_desc = "可控制" if selected_type_label == "🎮 控制面板" else "有效监测"
            st.warning(f"该设备下没有【{selected_type_label}】类型的{mode_desc}设备。")
    st.subheader("📊 跨棚数据对比")
    st.caption("选择传感器，从数据库拉取历史数据绘制趋势对比曲线。")
    valid_metric_names = set()
    for d in st.session_state.device_data:
        sensors_list = d.get('sensorsList') or []
        for s in sensors_list:
            if s.get('sensorTypeId') == 1 and str(s.get("value")) not in ['0', '0.0']:
                valid_metric_names.add(s.get("sensorName"))
                
    metric_opts = sorted(list(valid_metric_names))
    col_m1, col_m2 = st.columns([2, 1])
    
    if not metric_opts:
        st.info("当前设备未挂载有效的环境传感器数据。")
    else:
        with col_m1:
            selected_metric = st.selectbox("🎯 选择对比指标", metric_opts)
        with col_m2:
            # 增加时间维度筛选
            time_range = st.selectbox(
                "🕒 时间范围", 
                ["当前1小时", "今日", "最近一周", "最近一月"],
                index=1  # 默认选择“今日”
            )
        now = datetime.now()
        if time_range == "当前1小时":
            start_time = now - timedelta(hours=1)
        elif time_range == "今日":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "最近一周":
            start_time = now - timedelta(days=7)
        else:  # 最近一月
            start_time = now - timedelta(days=30)

        st.caption(f"📅 统计范围：{start_time.strftime('%Y-%m-%d %H:%M:%S')} 至 现在")
        line_chart_data = []
        with st.spinner("正在从数据库拉取历史时序数据..."):
            # 方式 1 本地数据库查询（推荐，效率更高）
            import database_manager # 确保引入了你的数据库模块
            # 方式 2 从 在线数据库中查找
            import db_manager
            for d in st.session_state.device_data:
                gh_name = d.get("deviceName", "未知大棚")
                sensors_list = d.get('sensorsList') or []
                
                # 精确匹配传感器名称，获取其专属 ID
                target_sensor = next((s for s in sensors_list if s.get("sensorName") == selected_metric), None)
                if target_sensor:
                    sensor_id = target_sensor.get("id")
                    # 依据 sensor_id 查询数据库中的历史记录
                    # history_records = database_manager.get_sensor_history(sensor_id, start_str, end_str)
                    history_records = db_manager.get_sensor_history_tidb(sensor_id, start_time, now)
                    
                    for record in history_records:
                        line_chart_data.append({
                            "温室名称": gh_name,
                            "采集时间": record["add_time"], # 数据库返回的字段
                            "数值": float(record["value"]),
                            "单位": target_sensor.get("unit")
                        })
        if line_chart_data:
            df_plot = pd.DataFrame(line_chart_data)
            df_plot["采集时间"] = pd.to_datetime(df_plot["采集时间"])
            df_plot["数值"] = pd.to_numeric(df_plot["数值"], errors='coerce')
            unit_str = line_chart_data[0].get("单位", "")

            # 1. 自动日期探测
            now = datetime.now()
            actual_min_date = df_plot["采集时间"].min().date()
            actual_max_date = df_plot["采集时间"].max().date()
            # 计算数据实际跨越的天数
            date_span = (actual_max_date - actual_min_date).days

            days_map = {"最近一周": 7, "最近一月": 30}
            if time_range in days_map:
                theory_start = (now - timedelta(days=days_map[time_range])).date()
                if actual_min_date > theory_start:
                    st.info(f"💡 数据库最早记录为 **{actual_min_date}**，已为您展示至今趋势。")
                # --- 2. 核心：智能频率判断 ---
                if date_span < 1:
                    # 💡 逻辑修正：如果实际数据不足 2 天，按“小时”聚合，防止出现“糖葫芦”点图
                    sample_rule = '1h' 
                    x_col = "采集时间"
                    is_category = False
                    axis_format = "%m-%d %H:%M"
                else:
                    # 正常跨天数据，按“天”聚合
                    sample_rule = '1d'
                    x_col = "日期标签"
                    is_category = True
                    axis_format = "%m-%d"
                final_df_list = []
                for gh in df_plot["温室名称"].unique():
                    gh_df = df_plot[df_plot["温室名称"] == gh].set_index("采集时间")
                    resampled = gh_df["数值"].resample(sample_rule).mean().reset_index()
                    if is_category:
                        resampled["日期标签"] = resampled["采集时间"].dt.strftime('%m-%d')
                    resampled["温室名称"] = gh
                    final_df_list.append(resampled)
                
                df_curve = pd.concat(final_df_list).dropna(subset=["数值"])
                df_curve = df_curve.sort_values("采集时间")
            else:
                # 当前1小时/今日：原始精度
                df_curve = df_plot.copy().sort_values("采集时间")
                x_col = "采集时间"
                is_category = False
                axis_format = "%H:%M"

            # --- 3. 渲染图表 ---
            if not df_curve.empty:
                
                sorted_gh_names = sorted(df_curve["温室名称"].unique(), key=extract_gh_num)
                fig_curve = px.line(
                    df_curve, x=x_col, y="数值", color="温室名称",
                    title=f"📈 {time_range} 各棚【{selected_metric}】趋势对比",
                    markers=True,
                    category_orders={"温室名称": sorted_gh_names}
                )
                if is_category:
                    fig_curve.update_xaxes(type='category', categoryorder='category ascending')
                else:
                    fig_curve.update_xaxes(tickformat=axis_format)

                fig_curve.update_layout(
                    xaxis_title="", 
                    yaxis_title=f"数值 ({unit_str})" if unit_str else "数值",
                    hovermode="x unified",
                    margin=dict(l=20, r=20, t=40, b=20)
                )
                
                fig_curve.update_traces(hovertemplate='%{y:.2f}') 
                st.plotly_chart(fig_curve, width='stretch')

# ----------------- 页面二：单棚孪生与控制 -----------------
# elif menu == "🎮 单棚孪生与控制 (管细节)":
#     st.header("🎮 单棚详情与操控")
#     device_names = [d['deviceName'] for d in st.session_state.device_data]
#     selected_gh = st.selectbox("目标大棚切换", device_names)
#     target_device = next(d for d in st.session_state.device_data if d['deviceName'] == selected_gh)
#     sensors = target_device.get('sensorsList', [])
    
#     col_view, col_ctrl = st.columns([2, 1])
    
#     with col_view:
#         # 【需求7】摄像头
#         st.subheader("📹 视频流与 3D 孪生")
#         st.video("https://www.w3schools.com/html/mov_bbb.mp4") # 占位
#         # 【需求2】实物建模
#         st.info("💡 3D 沙盘区域：此处通过 iframe 嵌入 Three.js 渲染的模型网页。")
        
#         # st.subheader("📟 实时环境数据")
#         # m_col1, m_col2, m_col3 = st.columns(3)
#         # temp, tu = get_sensor_info(sensors, "1号空温")
#         # hum, hu = get_sensor_info(sensors, "1号空湿")
#         # m_col1.metric("空气温度", f"{temp} {tu}")
#         # m_col2.metric("空气湿度", f"{hum} {hu}")
#     # TODO 这个也是正常的，但是需要美化修改
#     with col_ctrl:
#         # 【需求5】单设备操控
#         st.subheader("🎛️ 控制面板")
#         st.caption(f"当前在线状态: {'✅' if target_device.get('isLine') else '❌'}")
#         for s in sensors:
#             if s.get("sensorTypeId") == 2: # 控制类设备
#                 name = s.get("sensorName")
#                 state = (s.get("value") == "1")
#                 # Streamlit toggle 按钮
#                 toggled = st.toggle(f"🔌 {name}", value=state, key=f"sw_{s.get('id')}")
#                 # 【需求11】联动农事绑定 (核心逻辑体现)
#                 if toggled and not state: # 刚被打开
#                     if "雾化" in name:
#                         with st.expander("📝 记录：降温加湿工单 (系统检测到雾化开启)", expanded=True):
#                             st.text_input("操作员", "admin")
#                             st.number_input("预计开启时长(分钟)", min_value=1, value=30)
#                             st.button("提交记录", key=f"btn_{s.get('id')}")
#                     elif "卷被" in name or "卷膜" in name:
#                         with st.expander("📝 记录：通风保温工单 (系统检测到卷膜动作)", expanded=True):
#                             st.selectbox("操作意图", ["早晨见光", "夜间保温", "强风收拢"])
#                             st.button("提交记录", key=f"btn_{s.get('id')}")

# ----------------- 页面三：多维数据分析 -----------------
elif menu == "📈 多维数据分析 (查根因)":
    st.header("📈 多维数据分析看板")
    st.caption("基于平台全量实时数据与历史数据，进行深度农业参数分析。")
    
    # ================= 1. 全局动态提取有效的传感器选项 =================
    valid_metrics = set()      # 用于相关性分析（精确全名，如 "1号空温"）
    base_metrics = set()       # 用于区域聚合（提取后缀，如 "空温", "土壤ec"）
    
    if st.session_state.device_data:
        for d in st.session_state.device_data:
            for s in d.get('sensorsList', []):
                # 过滤出环境传感器，且过滤掉 '0' 和 '0.0' 的无效值
                if s.get('sensorTypeId') == 1 and str(s.get("value")) not in ['0', '0.0']:
                    name = s.get("sensorName", "")
                    valid_metrics.add(name)
                    if "号" in name:
                        base_metrics.add(name.split("号")[-1])
                    elif "组" in name:
                        base_metrics.add(name.split("组")[-1])
                    else:
                        base_metrics.add(name)
                        
    metric_opts = sorted(list(valid_metrics))
    base_metric_opts = sorted(list(base_metrics))
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 分析时间跨度")
    analysis_range = st.sidebar.selectbox(
        "选择分析的历史周期", 
        ["最近24小时", "最近一周", "最近一月"], 
        index=1
    )

    now = datetime.now()
    days_map = {"最近24小时": 1, "最近一周": 7, "最近一月": 30}
    start_time = now - timedelta(days=days_map[analysis_range])
    if not metric_opts:
        st.warning("⚠️ 当前没有任何有效的环境传感器数据可供分析。")
        st.stop()
        
    # ================= 2. 渲染三大分析模块 =================
    tab1, tab2, tab3 = st.tabs(["📊 传感器参数相关性分析", "📉 前中后区域聚合", "📥 历史数据导出"])
    with tab1: # TODO 加单位
        # ---------------- 【需求3】参数相关性分析 ----------------
        st.subheader("参数相关性分析")
        st.markdown("通过对比各棚的传感器数据，找到两个传感器数据之间的相关性。")

        device_names = [d.get("deviceName", "未知") for d in st.session_state.device_data]
        device_names = sorted(list(set(device_names)))

        c_gh, c1, c2 = st.columns(3)
        selected_gh = c_gh.selectbox("🏠 选择分析目标", device_names)
        dynamic_metric_opts = []
        target_device = next((d for d in st.session_state.device_data if d.get("deviceName") == selected_gh), None)
        if target_device :
            for s in target_device["sensorsList"]:
                s_name = s.get("sensorName")
                if s.get("sensorTypeId") != 1 or s.get("value") in ['0', '0.0']:
                    continue
                dynamic_metric_opts.append(s_name)    
            dynamic_metric_opts = sorted(list(set(dynamic_metric_opts)))
            print(f"🔍 可用于分析的传感器选项: {dynamic_metric_opts}")
        # 2. 渲染下拉框
        if dynamic_metric_opts:
            default_y_index = 1 if len(dynamic_metric_opts) > 1 else 0
            x_metric = c1.selectbox("横坐标 - 例如光照", dynamic_metric_opts, index=0)
            y_metric = c2.selectbox("纵坐标 - 例如温度", [metric for metric in dynamic_metric_opts if metric != x_metric], index=default_y_index)
            with st.spinner(f"正在拉取【{selected_gh}】自 {start_time.strftime('%Y-%m-%d %H:%M')} 以来的历史数据..."):
                db_manager.init_db() 
                conn = db_manager.get_connection()
                history_records = []      
                try:
                    with conn.cursor() as cursor:
                        sql = """
                            SELECT 
                                sh.add_time AS record_time, 
                                s.sensor_name, 
                                sh.value AS sensor_value 
                            FROM sensor_history sh
                            JOIN sensors s ON sh.sensor_id = s.sensor_id
                            JOIN devices d ON s.device_id = d.device_id
                            WHERE d.gh_name = %s 
                              AND sh.add_time >= %s
                              AND s.sensor_name IN (%s, %s)
                        """
                        cursor.execute(sql, (selected_gh, start_time, x_metric, y_metric))
                        history_records = cursor.fetchall()
                except Exception as e:
                    st.error(f"数据库查询失败: {e}")
                finally:
                    conn.close()
                if not history_records:
                    st.info(f"暂无【{selected_gh}】在此时段内的历史数据。")
                else:
                    df_raw, actual_start, actual_end = process_history_records(
    history_records, start_time, analysis_range
)
                    if not df_raw.empty:
                        df_pivot = df_raw.pivot_table(
                            index='record_time', 
                            columns='sensor_name', 
                            values='sensor_value',
                            aggfunc='mean'
                        ).reset_index()
                        if x_metric in df_pivot.columns and y_metric in df_pivot.columns:
                            df_corr = df_pivot[['record_time', x_metric, y_metric]].dropna()
                            df_corr.rename(columns={"record_time": "采集时间"}, inplace=True)
                            df_corr['采集时间'] = pd.to_datetime(df_corr['采集时间']).dt.strftime('%Y-%m-%d %H:%M')
                            
                            if len(df_corr) < 3: 
                                st.warning(f"⚠️ 当前时间跨度内，有效的对比数据过少（仅 {len(df_corr)} 条），无法进行回归分析。")
                            else:
                                fig_scatter = px.scatter(
                                    df_corr, 
                                    x=x_metric, 
                                    y=y_metric, 
                                    hover_name="采集时间", 
                                    trendline="lowess", 
                                    color_discrete_sequence=["#1f77b4"],
                                    title=f"【{selected_gh}】历史相关性：{x_metric} vs {y_metric}"
                                )
                                fig_scatter.update_traces(
                                    marker=dict(size=10, opacity=0.6), 
                                    selector=dict(mode="markers") # 选择器：只对点生效
                                )
                                fig_scatter.update_traces(
                                    line=dict(color="#ff7f0e", width=2), # 换成醒目的亮橙色，并稍微加粗
                                    selector=dict(mode="lines") # 选择器：只对线生效
                                )
                                st.plotly_chart(fig_scatter, width='stretch')
                                r_value = df_corr[x_metric].corr(df_corr[y_metric], method='spearman') # 计算 Spearman 相关系数
                                if pd.isna(r_value):
                                    st.info("💡 **系统智能分析**：\n\n数据点方差不足（数值在此期间几乎无变化），无法计算有效相关性。")
                                else:
                                    if r_value > 0.7:
                                        insight = "呈现 **强正相关** 📈。"
                                    elif r_value > 0.3:
                                        insight = "呈现 **中弱度正相关** ↗️。两者存在一定的**同向变化趋势**，但步调并非完全一致，可能还受到其他环境变量的交织影响。"
                                    elif r_value > -0.3:
                                        insight = "呈现 **无明显趋势关联** ➖。说明这两个参数之间在此期间既没有明显的跟随变化，也没有明显的反向制约关系。"
                                    elif r_value > -0.7:
                                        insight = "呈现 **中度负相关** ↘️。两者存在一定的**反向制约趋势**，一个处于高位时，另一个往往处于低位。"
                                    else:
                                        insight = "呈现 **强负相关** 📉。两者之间存在极强的**此消彼长**效应。"
                                    st.info(f"💡 **系统智能分析 (Spearman 秩相关)**：\n\n经计算，本周期内 {x_metric} 与 {y_metric} 的相关系数(rho)为 **{r_value:.2f}**，{insight}")
                            # heat map 两两分析其实和先去指标一样
                            # corr_matrix = df_corr[[x_metric, y_metric]].corr(method='spearman')
                            # fig_heatmap = px.imshow(corr_matrix, text_auto=True, \
                            #     color_continuous_scale='RdBu', title=f"{str_start} 至 {str_end} 期间【{selected_gh}】下 {x_metric} 和 {y_metric} 相关性矩阵")
                            # st.plotly_chart(fig_heatmap, width='stretch')

                    else:
                        st.info(f"获取的历史数据中未包含【{x_metric}】或【{y_metric}】的有效交叉数据。")
        else:
            c1.warning(f"⚠️ 【{selected_gh}】下暂无连续型环境传感器数据") 
    with tab2:
        # ---------------- 【需求3】前中后区域聚合分析 (全周期 + 多棚对比) ----------------
        st.subheader("全局大棚微气候区域传感器数据分析 (前/中/后)")
        st.markdown(
            "基于左侧选择的历史周期，计算各棚前、中、后区域的历史平均数值，横向对比全局大棚微气候状况。"
        )
        agg_base = st.selectbox(
            "请选择要聚合的指标基类",
            base_metric_opts,
            key="tab2_agg_base"
        )
        with st.spinner(
            f"正在拉取全局大棚自 {start_time.strftime('%Y-%m-%d %H:%M')} 以来的历史数据..."
        ):
            db_manager.init_db()
            conn = db_manager.get_connection()
            history_records = []
            try:    
                with conn.cursor() as cursor:
                    sql = """
                        SELECT
                            d.gh_name,
                            s.sensor_name,
                            sh.value AS sensor_value,
                            sh.add_time AS record_time  
                        FROM sensor_history sh  
                        JOIN sensors s
                            ON sh.sensor_id = s.sensor_id   
                        JOIN devices d
                            ON s.device_id = d.device_id    
                        WHERE sh.add_time >= %s
                    """ 
                    cursor.execute(sql, (start_time,))  
                    history_records = cursor.fetchall() 
            except Exception as e:  
                st.error(f"数据库查询失败: {e}")    
            finally:    
                conn.close()
            if not history_records: 
                st.info(f"暂无此时段内的【{agg_base}】历史数据。")  
            else:

                df_raw = pd.DataFrame(history_records)
                df_raw['sensor_value'] = pd.to_numeric(
                    df_raw['sensor_value'],
                    errors='coerce'
                )

                df_raw['record_time'] = pd.to_datetime(
                    df_raw['record_time']
                )

                df_raw['record_time'] = df_raw[
                    'record_time'
                ].dt.round('10min')

                df_raw = df_raw[
                    df_raw['sensor_name'].str.contains(
                        agg_base,
                        na=False
                    )
                ]

                df_raw['区域'] = df_raw[
                    'sensor_name'
                ].apply(parse_zone)

                df_clean = df_raw.dropna(
                    subset=['区域', 'sensor_value']
                )

                if df_clean.empty:
                    st.warning(
                        "数据清洗后无有效区域数据可供绘图。"
                    )

                else:
                    actual_start = df_clean['record_time'].min()
                    actual_end = df_clean['record_time'].max()
                    if (
                        actual_start - start_time
                    ).total_seconds() > 7200:
                        str_start = actual_start.strftime(
                            '%Y-%m-%d %H:%M'
                        )
                        str_end = actual_end.strftime(
                            '%Y-%m-%d %H:%M'
                        )
                        st.info(
                            f"💡 数据区间动态调整："
                            f"实际数据区间为 "
                            f"{str_start} 至 {str_end}"
                        )
                    df_agg = (
                        df_clean
                        .groupby(
                            ['gh_name', '区域']
                        )['sensor_value']
                        .mean()
                        .reset_index()
                    )
                    df_agg.rename(
                        columns={
                            'gh_name': '温室',
                            'sensor_value': '数值'
                        },
                        inplace=True
                    )

                    zone_order = [
                        "前区(1号/1组)",
                        "中区(2号/2组)",
                        "后区(3号/3组)"
                    ]

                    df_agg['区域'] = pd.Categorical(
                        df_agg['区域'],
                        categories=zone_order,
                        ordered=True
                    )
                    df_agg = df_agg.sort_values(
                        ['温室', '区域']
                    )
                    fig_agg = px.bar(

                        df_agg,

                        x="温室",

                        y="数值",

                        color="区域",

                        barmode="group",

                        text_auto='.2f',
                        title=f"各棚【{agg_base}】前中后区域分布 (历史均值)",
                        color_discrete_sequence=[
                            "#636EFA",
                            "#00CC96",
                            "#EF553B"
                        ]
                    )
                    # 动态Y轴
                    y_min = df_agg['数值'].min() * 0.95

                    fig_agg.update_layout(
                        yaxis_title=f"平均 {agg_base} 数值",
                        yaxis=dict(
                            range=[y_min, None]
                        )
                    )

                    st.plotly_chart(
                        fig_agg,
                        width='stretch'
                    ) 
    with tab3:
        # ---------------- 【需求3】自定义时段与历史数据导出 ----------------
        st.subheader("自定义时段与历史数据导出")
        st.caption("从数据库提取历史时序数据，支持按大棚/传感器/组合导出，可一键下载 CSV。")

        col_ex1, col_ex2, col_ex3, col_ex4 = st.columns([2, 2, 3, 1])

        # 1️⃣ 选择大棚（可选 "所有大棚"）
        device_names = ["所有大棚"] + [d['deviceName'] for d in st.session_state.device_data]
        export_gh = col_ex1.selectbox("选择大棚", device_names)

        # 2️⃣ 选择传感器（可选 "所有传感器"）
        sensor_names = ["所有传感器"] + metric_opts
        export_sensor_name = col_ex2.selectbox("选择传感器", sensor_names)

        # 3️⃣ 自定义时间段
        date_range = col_ex3.date_input(
            "选择时间范围", 
            value=(datetime.now() - timedelta(days=1), datetime.now())
        )
        # 4️⃣ 导出按钮
        export_btn = col_ex4.button("🔍 查询并导出", type="primary")
        if export_btn:
            if len(date_range) != 2:
                st.warning("请选择完整的起止日期。")
            else:
                start_date, end_date = date_range
                start_str = start_date.strftime("%Y-%m-%d 00:00:00")
                end_str = end_date.strftime("%Y-%m-%d 23:59:59")

                with st.spinner("正在从数据库检索数据..."):
                    import database_manager

                    # 构建查询条件
                    sql_filters = []
                    query_params = []

                    # 大棚过滤
                    if export_gh != "所有大棚":
                        sql_filters.append("d.gh_name = %s")
                        query_params.append(export_gh)
                    if export_sensor_name != "所有传感器":
                        sql_filters.append("s.sensor_name = %s")
                        query_params.append(export_sensor_name)
                    # 时间过滤
                    sql_filters.append("sh.add_time BETWEEN %s AND %s")
                    query_params.extend([start_str, end_str])

                    # SQL组合
                    where_clause = " AND ".join(sql_filters)
                    sql = f"""
                        SELECT 
                            d.gh_name AS 温室,
                            s.sensor_name AS 传感器,
                            sh.value AS 数值,
                            sh.add_time AS 采集时间,
                            s.unit AS 单位
                        FROM sensor_history sh
                        JOIN sensors s ON sh.sensor_id = s.sensor_id
                        JOIN devices d ON s.device_id = d.device_id
                        WHERE {where_clause}
                        ORDER BY d.gh_name, s.sensor_name, sh.add_time
                    """
                    # 查询数据库
                    try:
                        db_manager.init_db()
                        conn = db_manager.get_connection()
                        with conn.cursor() as cursor:
                            cursor.execute(sql, query_params)
                            rows = cursor.fetchall()
                        conn.close()
                    except Exception as e:
                        st.error(f"数据库查询失败: {e}")
                        rows = []

                    if not rows:
                        st.warning("未检索到符合条件的数据。")
                    else:
                        # 转 DataFrame
                        df_export = pd.DataFrame(rows)
                        df_export['数值'] = pd.to_numeric(df_export['数值'], errors='coerce')
                        df_export['采集时间'] = pd.to_datetime(df_export['采集时间']).dt.strftime('%Y-%m-%d %H:%M:%S')
                        df_export['单位'] = df_export['单位'].fillna("")

                        # 显示表格
                        st.success(f"✅ 成功提取 {len(df_export)} 条记录！")
                        st.dataframe(df_export, height=300)

                        # 下载 CSV
                        csv_data = df_export.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📥 下载 CSV",
                            data=csv_data,
                            file_name=f"历史数据_{export_gh}_{export_sensor_name}.csv",
                            mime="text/csv"
                        )


# ----------------- 页面四：批次工单与联控 -----------------
elif menu == "📋 批次工单与联控 (抓生产)":
    st.header("📋 批量生产与批次管理")
    
    col1, col2 = st.columns(2, gap="large")
    with col1:
        # ================= 【需求6】多设备联控 =================
        st.subheader("🚀 多设备一键联控")
        st.caption("勾选多个目标，系统将自动识别可控硬件并并发下发指令。")
        online_devices = [d['deviceName'] for d in st.session_state.device_data if d.get('isLine') == 1]
        
        if not online_devices:
            st.error("当前无在线设备可控！")
        else:
            target_ghs = st.multiselect("1. 勾选需要联控的在线温室", online_devices, default=online_devices[0:1] if online_devices else None)

            switch_names = set()
            for d in st.session_state.device_data:
                if d.get('deviceName') in target_ghs:
                    sensors = d.get('sensorsList') or []
                    for s in sensors:
                        if s.get('sensorTypeId') == 2:
                            name = s.get("sensorName")
                            if name:switch_names.add(name)
            action_options = []
            if switch_names:
                for name in sorted(list(switch_names)):
                    action_options.append(f"🟢 打开所有 {name}")
                    action_options.append(f"🔴 关闭所有 {name}")
            else:
                action_options = ["⚠️ 选中的大棚暂无可控设备"]

            action = st.selectbox("2. 自动识别并选择统一执行的动作", action_options)
            if st.button("🚀 下发联控指令", type="primary", width='stretch'):
                if not target_ghs:
                    st.warning("请至少选择一个温室！")
                elif "⚠️" in action:
                    st.error("当前无有效指令可下发。")
                else:
                        if st.session_state.get("api_client") is None:
                            try:
                                client = IotClient() 
                                login_res = client.login(USERNAME, PASSWORD, API_KEY)
                                if login_res.get("flag") == "00":
                                    token_res = client.get_access_token(USERNAME, PASSWORD)
                                    if token_res.get("flag") == "00":
                                        st.session_state["api_client"] = client
                                    else:
                                        st.error("❌ 获取访问令牌失败。")
                                        st.stop()
                                else:
                                    st.error("❌ 云端平台登录失败。")
                                    st.stop()
                            except Exception as e:
                                st.error(f"客户端初始化发生异常: {e}")
                                st.stop()  
                        api_client = st.session_state.get("api_client")
                        if api_client:
                            is_open = "打开" in action
                            target_switcher_val = 1 if is_open else 0
                            target_sensor_name = action.replace("🟢 打开所有 ", "").replace("🔴 关闭所有 ", "")
                            success_cnt, fail_cnt, skip_cnt, details_log = execute_batch_control(
                                client=api_client, 
                                target_ghs=target_ghs, 
                                target_sensor_name=target_sensor_name, 
                                target_switcher_val=target_switcher_val, 
                            )
                            summary_msg = f"操作完毕。成功指令: **{success_cnt}**"
                            if skip_cnt > 0:
                                summary_msg += f"，拦截冗余指令: **{skip_cnt}** (已是目标状态)"
                            if fail_cnt > 0:
                                summary_msg += f"，失败: **{fail_cnt}**"
                                
                            if fail_cnt == 0 and success_cnt > 0:
                                st.success(f"✅ {summary_msg}")
                            elif fail_cnt > 0:
                                st.warning(f"⚠️ {summary_msg}。请检查失败设备网络。")
                            elif success_cnt == 0 and skip_cnt > 0:
                                st.success(f"✅ 所选大棚设备已经全部处于目标状态，无需重复下发指令。")
                            else:
                                st.error("❌ 未匹配到可控的物理设备实体。")
                            
                            if details_log:
                                st.dataframe(pd.DataFrame(details_log), width='stretch')
    with col2:
        db_manager.init_db()
        conn = db_manager.get_connection()
        active_batches_data = [] # 存储原始行数据
        active_batch_labels = [] # 存储显示用的字符串
        
        try:
            with conn.cursor() as cursor:
                # 查询所有正在进行中的种植批次
                cursor.execute("""
                    SELECT batch_id, gh_name, crop_name, variety, start_time, expected_harvest, current_stage 
                    FROM batches WHERE status = 1
                """)
                active_batches_data = cursor.fetchall()
                active_batch_labels = [f"ID:{b['batch_id']} | {b['gh_name']} - {b['crop_name']}({b['variety']})" for b in active_batches_data]
        finally:
            conn.close()

        # ================= 【需求9】电子工单模板：数据归档 =================
        st.subheader("📑 标准化电子工单")
        with st.form("sop_form", clear_on_submit=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            if not active_batch_labels:
                st.warning("⚠️ 暂无进行中的批次，请先在数据库中创建批次信息。")
                selected_batch_label = col1.selectbox("关联批次", ["无可用批次"], disabled=True)
            else:
                selected_batch_label = col1.selectbox("关联批次", active_batch_labels)
                
            task_type = col2.selectbox("作业类型 (SOP)", ["🌱 播种与定植", "💧 智能灌溉", "💊 水肥一体化施肥", "✂️ 打叶与采收", "🌀 强制通风"])
            duration = col3.number_input("耗时(分钟)", min_value=1, value=30)
            
            operator = st.text_input("操作负责人", placeholder="输入执行人姓名")
            details = st.text_area("作业明细内容", placeholder="例如：设定EC值1.5，开启侧窗通风30%...")
            
            submitted = st.form_submit_button("💾 生成并归档工单", type="primary", use_container_width=True)
            
            if submitted and active_batch_labels:
                # 解析选中的 batch_id 和 gh_name
                selected_batch = next(b for b in active_batches_data if f"ID:{b['batch_id']}" in selected_batch_label)
                
                conn = db_manager.get_connection()
                try:
                    with conn.cursor() as cursor:
                        sql = """
                            INSERT INTO work_orders (batch_id, gh_name, task_type, operator, content, duration_mins) 
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql, (
                            selected_batch['batch_id'], 
                            selected_batch['gh_name'], 
                            task_type, 
                            operator, 
                            details, 
                            duration
                        ))
                        conn.commit()
                    st.success(f"✅ 【{task_type}】工单已成功存入 TiDB 数据库，并关联至批次 {selected_batch['batch_id']}！")
                except Exception as e:
                    st.error(f"工单存入失败: {e}")
                finally:
                    conn.close()

        st.divider()

        # ================= 【需求10】批次管理与生长曲线：真实数据关联 =================
        st.subheader("📦 农作物批次与生长曲线关联")
        st.caption("系统自动根据批次的【定植时间】截取历史环境数据，并进行生长阶段标注。")
        
        if not active_batch_labels:
            st.info("尚未选择任何种植批次。")
        else:
            c_b1, c_b2 = st.columns([1, 3])
            
            with c_b1:
                selected_track_label = st.selectbox("选择要追踪的批次", active_batch_labels, key="track_batch")
                batch = next(b for b in active_batches_data if f"ID:{b['batch_id']}" in selected_track_label)
                
                # 自动计算批次指标
                runtime_days = (datetime.now() - batch['start_time']).days
                st.metric("批次运行时长", f"{runtime_days} 天")
                
                if batch['expected_harvest']:
                    days_left = (batch['expected_harvest'] - datetime.now()).days
                    st.metric("预计采收倒计时", f"{days_left} 天", delta_color="inverse")
                
                st.write(f"**当前阶段**: `{batch['current_stage'] or '未标注'}`")

            with c_b2:
                # 🌟 核心逻辑：从数据库拉取该批次在该大棚的真实环境曲线
                with st.spinner("正在回溯该批次的历史生长环境数据..."):
                    conn = db_manager.get_connection()
                    batch_history = []
                    try:
                        with conn.cursor() as cursor:
                            # 查找该大棚下名为“温度”或“空温”的传感器 ID
                            cursor.execute("""
                                SELECT s.sensor_id FROM sensors s 
                                JOIN devices d ON s.device_id = d.device_id 
                                WHERE d.gh_name = %s AND (s.sensor_name LIKE '%%温度%%' OR s.sensor_name LIKE '%%空温%%')
                                LIMIT 1
                            """, (batch['gh_name'],))
                            res_s = cursor.fetchone()
                            
                            if res_s:
                                sensor_id = res_s['sensor_id']
                                # 截取从 start_time 至今的该传感器所有历史值
                                cursor.execute("""
                                    SELECT add_time, value FROM sensor_history 
                                    WHERE sensor_id = %s AND add_time >= %s 
                                    ORDER BY add_time ASC
                                """, (sensor_id, batch['start_time']))
                                batch_history = cursor.fetchall()
                    finally:
                        conn.close()

                if not batch_history:
                    st.warning(f"⚠️ 在【{batch['gh_name']}】中未找到该批次对应的历史温度数据。")
                else:
                    df_b = pd.DataFrame(batch_history)
                    df_b['value'] = pd.to_numeric(df_b['value'], errors='coerce')
                    df_b['add_time'] = pd.to_datetime(df_b['add_time'])
                    
                    # 绘制真实曲线
                    fig_batch = px.line(df_b, x='add_time', y='value', 
                                    title=f"批次 {batch['batch_id']} 环境回溯 ({batch['crop_name']})",
                                    labels={"add_time": "生长日期", "value": "空气温度 (℃)"})
                    
                    # 🌟 自动化生长阶段标注 (以生菜为例，天数可根据 crop_name 动态调整)
                    start_date = batch['start_time']
                    if "生菜" in batch['crop_name']:
                        # 缓苗期: 前7天
                        fig_batch.add_vrect(x0=start_date, x1=start_date + timedelta(days=7), 
                                        fillcolor="green", opacity=0.1, line_width=0, annotation_text="🌱 缓苗期")
                        # 莲座期: 7-25天
                        fig_batch.add_vrect(x0=start_date + timedelta(days=7), x1=start_date + timedelta(days=25), 
                                        fillcolor="yellow", opacity=0.1, line_width=0, annotation_text="🌿 莲座期")
                        # 结球期: 25天以后
                        if runtime_days > 25:
                            fig_batch.add_vrect(x0=start_date + timedelta(days=25), x1=datetime.now(), 
                                            fillcolor="orange", opacity=0.1, line_width=0, annotation_text="🥬 结球期")

                    fig_batch.update_layout(height=350, margin={"t":40, "b":0})
                    st.plotly_chart(fig_batch, use_container_width=True)
            
# ----------------- 页面五：策略与预警 -----------------
elif menu == "⚙️ 策略与预警 (设规则)":
    st.header("⚙️ 自动化策略与报警配置")
    st.markdown("### 第一步：选择通知接收方式")
    push_mode = st.radio(
        "您希望如何接收报警消息？",
        ["加入官方公共运维群 (推荐)", "自定义私有钉钉群"],
        horizontal=True,
        help="公共群只需扫码即可；私有群需要您自行创建机器人并提供 Webhook 地址。"
    )
    final_webhook = ""
    # 你的硬编码 Webhook (官方群)
    OFFICIAL_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=887648e45f915aca4617e5958a69171d6f3389cc320fe8253cc36460121ae925"
    if push_mode == "加入官方公共运维群 (推荐)":
        _, col_mid, _ = st.columns([1, 4, 1])
        with col_mid:
            with st.expander("📢 扫码入群即可接收通知", expanded=True):
                c_qr, c_info = st.columns([1.2, 2])
                c_qr.image("imgs/qrcode.png", caption="官方运维群二维码", width='stretch')
                c_info.markdown("<br>", unsafe_allow_html=True)
                c_info.info("""
                **使用须知：**
                1. 扫码进入【平台预警官方群】。
                2. 系统已内置机器人，无需任何配置。
                3. 请在下方保存规则，即可开始接收推送。
                """)
        final_webhook = OFFICIAL_WEBHOOK
    else:
        _, col_mid, _ = st.columns([1, 4, 1])
        with col_mid:
            with st.expander("🛠️ 自建机器人配置指引", expanded=True):
                st.info("""
                **操作指引：**
                1. 在您的钉钉群：设置 -> 智能群助手 -> 添加机器人 -> 自定义。
                2. 安全设置：勾选 **【自定义关键词】**，输入：**预警**。
                3. 复制生成的 Webhook 地址填入下方。
                """)
                user_webhook = st.text_input(
                    "请输入您的 Webhook 地址", 
                    placeholder="https://oapi.dingtalk.com/robot/send?access_token=...",
                    label_visibility="visible"
                )
                if user_webhook:
                    user_webhook_check(user_webhook)
                else:
                    st.warning("⚠️ 请输入 Webhook 地址以继续配置。")
                    final_webhook = ""
    # ================= 2. 规则配置表单 =================
    st.write("---")
    st.write("---")
    st.markdown("### 第二步：设定报警阈值")
    st.info("💡 提示：指定大棚的规则优先级高于全局规则。如果该大棚已有特定规则，全局设置将不会覆盖它。")
    sensor_category = st.radio(
        "👉 请先选择要配置的传感器大类：",
        ["📊 数值型 (如温湿度、光强、PH值)", "🎛️ 开关/状态型 (如设备启停、漏水状态)"],
        horizontal=True
    )
    if "数值型" in sensor_category:
        target_types = 1
    else:
        target_types = 2
    gh_names = ["所有大棚"] + [d['deviceName'] for d in get_sorted_devices(st.session_state.device_data)]
    
    c1, c2 = st.columns(2)
    target_gh = c1.selectbox("应用范围", gh_names)
    # ================= 2. 严密的传感器提取逻辑 (交集 vs 单体) =================
    metric_info_map = {} # { "空温": {"unit": "℃", "type": 1} }
    metric_opts = []
    if target_gh == "所有大棚":
        # 【全局模式】：求所有大棚传感器的交集
        common_metrics = None # 用于存储交集
        for d in st.session_state.device_data:
            current_gh_metrics = set() # 当前大棚的传感器集合
            for s in d.get('sensorsList', []):
                if s.get('sensorTypeId') == target_types:
                    name = s.get("sensorName", "")
                    unit = s.get("unit", "")
                    base_name = re.sub(r'^\d+[号组]', '', name).strip()
                    if base_name:
                        current_gh_metrics.add(base_name)
                        metric_info_map[base_name] = {"unit": unit, "type": s.get('sensorTypeId') }
                    
            # 求交集算法
            if common_metrics is None:
                common_metrics = current_gh_metrics # 第一个大棚作为初始集合
            else:
                common_metrics = common_metrics.intersection(current_gh_metrics) # 连续求交集
        # 只保留公共的传感器
        metric_opts = sorted(list(common_metrics)) if common_metrics else []
    else:# 【局部模式】：只读取指定大棚的数值传感器且数值非零
        for d in st.session_state.device_data:
            if d['deviceName'] == target_gh:
                for s in d.get('sensorsList', []):
                    if s.get('sensorTypeId') == target_types:
                        name = s.get("sensorName", "")
                        unit = s.get("unit", "")
                        base_name = re.sub(r'^\d+[号组]', '', name).strip()
                        if base_name:
                            metric_info_map[base_name] = {"unit": unit, "type": s.get('sensorTypeId')}
                break
        metric_opts = sorted(list(metric_info_map.keys()))
    # ================= 3. 渲染配置表单 =================
    if not metric_opts:
        st.warning(f"⚠️ 在【{target_gh}】下，没有找到符合要求的 **{sensor_category.split(' ')[1]}** 传感器。")
        st.stop()
    target_metric = c2.selectbox("监控指标", metric_opts)
    current_info = metric_info_map.get(target_metric, {"unit": "", "type": 1})
    current_unit = current_info["unit"]
    data_type = current_info["type"]
    # 获取默认阈值配置 (仅针对数值型有用)
    current_cfg = {"unit": current_unit, "min": -10000.0, "max": 100000.0, "step": 1.0, "def_min": 0.0, "def_max": 100.0}
    if data_type == 1:
        for key, cfg in METRIC_BEHAVIOR.items():
            if target_metric and key in target_metric:
                current_cfg = cfg
                break
    form_key = f"{target_gh}_{target_metric}"
    with st.form(form_key):
        if target_gh == "所有大棚":
            st.write(f"正在配置：**🌍 全局通用** 的 **{target_metric}** 预警")
        else:
            st.write(f"正在配置：**📍 指定大棚 ({target_gh})** 的 **{target_metric}** 预警")
        if data_type == 1:
            st.caption(f"📏 数据单位：`{current_unit}`")
            v2, v1 = st.columns(2)
            max_v = v1.number_input(
                f"上限阈值 ({current_cfg['unit']})",
                min_value=float(current_cfg['min']),
                max_value=float(current_cfg['max']),
                value=float(current_cfg['def_max']),
                step=float(current_cfg['step'])
            )
            min_v = v2.number_input(
                f"下限阈值 ({current_cfg['unit']})",
                min_value=float(current_cfg['min']),
                max_value=float(current_cfg['max']),
                value=float(current_cfg['def_min']),
                step=float(current_cfg['step'])
            )
        else:
            st.info("💡 **开关/状态量报警**：请选择触发报警的目标状态。")
            status_choice = st.selectbox(
                "当状态变为以下值时报警：", 
                options=[1, 0], 
                format_func=lambda x: "🟢 开启状态" if x == 1 else "🔴 关闭状态"
            )
            max_v = float(status_choice)
            min_v = -999.0 
        
        submit = st.form_submit_button("🚀 部署预警策略", type="primary")
        # ================= 4. 提交保存逻辑 =================
        if submit:
            with st.spinner("正在写入云端规则..."):
                try:
                    db_manager.init_db() 
                    conn = db_manager.get_connection()
                    with conn.cursor() as cursor:
                        sql = """
                            INSERT INTO alert_rules
                            (
                                target_gh,
                                metric_name,
                                min_val,
                                max_val,
                                ding_webhook
                            )
                            VALUES (%s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            min_val=%s,
                            max_val=%s,
                            ding_webhook=%s
                        """
                        if target_gh == "所有大棚":
                            # 提取出所有真实存在的大棚名称
                            actual_targets = [d['deviceName'] for d in st.session_state.device_data]
                        else:
                            actual_targets = [target_gh]
                        # 遍历实际的大棚列表，逐个写入/更新规则
                        for gh in actual_targets:
                            cursor.execute(sql, (
                                gh,             # 动态分配的真实大棚名称 (如: 01号大棚)
                                target_metric,  # 比如: 空温 或 漏水传感器
                                min_v,
                                max_v,
                                final_webhook,  # Insert 参数
                                min_v,
                                max_v,
                                final_webhook   # Update 参数
                            ))
                            
                    conn.commit()
                    conn.close()
                    st.balloons()
                    
                    # 🌟 体验优化：根据是全局还是局部，给予不同的成功提示
                    if target_gh == "全局所有大棚":
                        st.success(f"✅ 已成功为 **{len(actual_targets)}** 个大棚批量部署【{target_metric}】的报警策略！")
                    else:
                        st.success(f"✅ 【{target_gh}】的【{target_metric}】报警策略部署成功！")

                except Exception as e:
                    st.error(f"⚠️ 保存失败: {e}")
                    



# 10. 批次管理：关联环境与生长曲线自动标注
# # 假设这是从你的 sensor_history 表中，提取该“批次”从种下到现在的真实日均温
# # select ... where add_time >= '批次开始时间'
# df_batch = pd.DataFrame({
#     '日期': pd.date_range(start='2026-03-01', periods=40),
#     '温度': [20 + (i*0.1) for i in range(40)] # 模拟温度略微上升
# })

# fig = px.line(df_batch, x='日期', y='温度', title="生菜批次-202603 生长环境曲线 (自动节点标注)")

# # 🌟 核心魔法：根据天数自动打上生长周期的底色标注
# fig.add_vrect(x0="2026-03-01", x1="2026-03-10", fillcolor="green", opacity=0.1, line_width=0, annotation_text="🌱 缓苗期")
# fig.add_vrect(x0="2026-03-10", x1="2026-03-30", fillcolor="yellow", opacity=0.1, line_width=0, annotation_text="🌿 莲座期")
# fig.add_vrect(x0="2026-03-30", x1="2026-04-10", fillcolor="orange", opacity=0.1, line_width=0, annotation_text="🥬 结球期")

# st.plotly_chart(fig, use_container_width=True)


                    
# 11. 远程控制与农事表单绑定（自动弹出）                   
# import streamlit as st

# # 1. 定义一个针对特定动作的弹窗表单 (例如通风表单)
# @st.dialog("📝 自动农事记录：通风换气")
# def ventilation_form(gh_name):
#     st.info(f"系统检测到您刚刚操作了【{gh_name}】的卷膜机。为规范管理，请补充通风记录。")
#     reason = st.selectbox("通风原因", ["常规换气", "高温降温", "降低湿度", "补充二氧化碳"])
#     target_time = st.number_input("预计通风时长 (分钟)", min_value=10, value=30)
    
#     if st.button("提交记录"):
#         # 执行插入 work_orders 表的操作
#         st.session_state.show_form = False # 关闭弹窗触发器
#         st.rerun() # 刷新页面关闭弹窗

# # 2. 在你原来的控制代码逻辑中，加入触发机制
# target_sensor_name = "1号卷膜机"
# action = "开启"

# if st.button("开启卷膜机"):
#     # 假设这里是你调用 API 下发成功的代码...
#     ctrl_success = True 
    
#     if ctrl_success:
#         st.success("✅ 指令下发成功！")
        
#         # 🌟 核心：识别操作的是什么设备，触发对应的弹窗
#         if "卷膜" in target_sensor_name and "开" in action:
#             # 激活并显示通风表单弹窗
#             ventilation_form(selected_gh)
            
#         elif "雾化" in target_sensor_name or "水泵" in target_sensor_name:
#             # 可以写一个 misting_form(selected_gh) 弹窗
#             st.toast("提示：请记录灌溉/降温数据", icon="💧")