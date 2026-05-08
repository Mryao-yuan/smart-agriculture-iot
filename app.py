import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import time
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as got

from sheduler import device_info_get
import database_manager 
from  utils import display_devices_grid,get_weather_amap,init_weather_alert_config,get_weather_alert
from datetime import datetime
from config import *
# ==================== 1. 基础配置与全局工具 ====================
st.set_page_config(page_title="智慧温室 AIoT 平台", layout="wide", page_icon="🌿")


# ==================== 2. Session 状态初始化 ====================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'device_data' not in st.session_state:
    st.session_state.device_data = [] # 存放拉取的真实设备数据

# ==================== 3. 侧边栏导航 ====================
with st.sidebar:
    st.title("🌿 智慧农业平台")
    # 页面路由菜单
    menu = st.radio("🏠 业务导航", [
        "🌐 设备整体状态", 
        "🎮 单棚孪生与控制 (管细节)", 
        "📈 多维数据分析 (查根因)", 
        "📋 批次工单与联控 (抓生产)",
        "⚙️ 策略与预警 (设规则)"
    ])
    # 检查是否有设备数据
    if not st.session_state.get('device_data'):
        st.warning("👈 请点击左侧【同步云端最新数据】获取设备信息。")
    
    st.divider()
    
    data = device_info_get() 
    st.session_state.device_data = data.get("dataList", [])

    if st.button("退出登录"):
        st.session_state.logged_in = False
        st.rerun()

# if not st.session_state.logged_in:
#     st.info("请先登录系统。")
#     

if not st.session_state.device_data:
    st.warning("👈 请点击左侧【同步云端最新数据】拉取平台台账。")

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
        
        # 假设你已经定义了 WEATHER_API_KEY
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
            submit_btn = st.form_submit_button("💾 保存配置", type="primary", use_container_width=True)
            
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
            
            # 【核心】：添加图层，即使 lats 和 lngs 是空的，也能强制在左上角渲染出图例！
            fig.add_trace(go.Scattermapbox(
                lat=lats,
                lon=lngs,
                mode='markers',
                marker=go.scattermapbox.Marker(size=14, color=config["color"]),
                name=config["name"], # 这里就是图例上显示的文字，如：正常 (9)
                hoverinfo="text",
                text=texts,
                showlegend=True 
            ))
        # 5. 获取地图初始中心点
        center_lat = float(st.session_state.device_data[0].get('lat', 36.73291))
        center_lng = float(st.session_state.device_data[0].get('lng', 101.74776))

        # 6. 配置地图底图和图例位置
        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox=dict(
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
        
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("暂无设备坐标数据")

    # ==================== 【需求2】联动查看单设备传感器详情 ====================
    st.subheader("🔍 设备传感器详细看板")
    st.caption("选择大棚，查看其挂载的所有实时传感器数据。")
    
    device_names = [d['deviceName'] for d in st.session_state.device_data]
    selected_gh = st.selectbox("👉 选择要查看的大棚", device_names)
    
    # 找到选中的那个设备的完整数据
    target_device = next(d for d in st.session_state.device_data if d['deviceName'] == selected_gh)
    sensors_list = target_device.get("sensorsList")
    
    if not sensors_list:
        st.info(f"暂未获取到 {selected_gh} 的传感器数据 (sensorsList 为 null)。")
    else:
        # 过滤出真正的传感器 (过滤掉开关类设备，假设 sensorTypeId == 1 为数值传感器)
        env_sensors = [s for s in sensors_list if s.get('sensorTypeId') == 1 and s.get("value") not in  ['0','0.0']]
        
        if env_sensors:
            # 使用栅格布局整齐地展示几十个传感器
            cols_sensor = st.columns(4) # 每行放 4 个传感器
            for idx, sensor in enumerate(env_sensors):
                s_name = sensor.get("sensorName", "未知")
                s_val = sensor.get("value", "--")
                s_unit = sensor.get("unit", "")
                
                with cols_sensor[idx % 4]:
                    # 用卡片样式包裹 metric，看起来更像独立仪表盘
                    st.markdown(f"""
                    <div style="background-color:#f8f9fa; padding:10px; border-radius:5px; margin-bottom:10px; border-left: 4px solid #1f77b4;">
                        <div style="font-size:14px; color:#666;">{s_name}</div>
                        <div style="font-size:24px; font-weight:bold; color:#333;">{s_val} <span style="font-size:14px; color:#999;">{s_unit}</span></div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("该设备下未挂载环境传感器。")
            
   
          
    # 【需求4】跨棚均值对比
    st.subheader("📊 主页跨棚数据对比 (需求4)")
    st.caption("选择传感器，从数据库拉取历史数据绘制趋势对比曲线。")
    
    valid_metric_names = set()
    for d in st.session_state.device_data:
        sensors_list = d.get('sensorsList') or []
        for s in sensors_list:
            if s.get('sensorTypeId') == 1 and str(s.get("value")) not in ['0', '0.0']:
                valid_metric_names.add(s.get("sensorName"))
                
    metric_opts = sorted(list(valid_metric_names))
    
    if not metric_opts:
        st.info("当前设备未挂载有效的环境传感器数据。")
    else:
        chart_metric = st.selectbox("👉 请选择要对比的传感器指标", metric_opts)
        # 2. 准备查询数据库的时间范围 (例如查询过去 24 小时)
        end_time = datetime.now()
        start_time = end_time - timedelta(days=1)
        start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 3. 基于精确的名字找到 ID，并从数据库拉取数据
        line_chart_data = []
        
        with st.spinner("正在从数据库拉取历史时序数据..."):
            import database_manager # 确保引入了你的数据库模块
            
            for d in st.session_state.device_data:
                gh_name = d.get("deviceName", "未知大棚")
                sensors_list = d.get('sensorsList') or []
                
                # 精确匹配传感器名称，获取其专属 ID
                target_sensor = next((s for s in sensors_list if s.get("sensorName") == chart_metric), None)
                
                if target_sensor:
                    sensor_id = target_sensor.get("id")
                    # 依据 sensor_id 查询数据库中的历史记录
                    history_records = database_manager.get_sensor_history(sensor_id, start_str, end_str)
                    for record in history_records:
                        line_chart_data.append({
                            "温室名称": gh_name,
                            "采集时间": record["add_time"], # 数据库返回的字段
                            "数值": float(record["value"]),
                            "单位": target_sensor.get("unit")
                        })
        
        # 4. 使用 Plotly 渲染趋势曲线图ue
        df_curve = pd.DataFrame(line_chart_data)
        
        if not df_curve.empty:
            # 确保时间列为 datetime 格式，防止图表 X 轴错乱
            df_curve["采集时间"] = pd.to_datetime(df_curve["采集时间"])
            
            fig_curve = px.line(
                df_curve, 
                x="采集时间", 
                y="数值", 
                color="温室名称",
                title=f"各棚 【{chart_metric}】 过去24小时趋势曲线",
                markers=True # 在折线上显示数据点
            )
            fig_curve.update_layout(
                xaxis_title="", 
                yaxis_title="传感器数值",
                hovermode="x unified" # 鼠标悬浮时，出现一条垂直线同时对比所有大棚的值
            )
            st.plotly_chart(fig_curve, use_container_width=True)
        else:
            st.warning("数据库中暂无该指标的历史数据，请确保后台同步脚本正在运行。")

# ----------------- 页面二：单棚孪生与控制 -----------------
elif menu == "🎮 单棚孪生与控制 (管细节)":
    st.header("🎮 单棚详情与操控")
    
    device_names = [d['deviceName'] for d in st.session_state.device_data]
    selected_gh = st.selectbox("目标大棚切换", device_names)
    target_device = next(d for d in st.session_state.device_data if d['deviceName'] == selected_gh)
    sensors = target_device.get('sensorsList', [])
    
    col_view, col_ctrl = st.columns([2, 1])
    
    with col_view:
        # 【需求7】摄像头
        st.subheader("📹 视频流与 3D 孪生")
        st.video("https://www.w3schools.com/html/mov_bbb.mp4") # 占位
        # 【需求2】实物建模
        st.info("💡 3D 沙盘区域：此处通过 iframe 嵌入 Three.js 渲染的模型网页。")
        
        # st.subheader("📟 实时环境数据")
        # m_col1, m_col2, m_col3 = st.columns(3)
        # temp, tu = get_sensor_info(sensors, "1号空温")
        # hum, hu = get_sensor_info(sensors, "1号空湿")
        # m_col1.metric("空气温度", f"{temp} {tu}")
        # m_col2.metric("空气湿度", f"{hum} {hu}")

    with col_ctrl:
        # 【需求5】单设备操控
        st.subheader("🎛️ 控制面板")
        st.caption(f"当前在线状态: {'✅' if target_device.get('isLine') else '❌'}")
        
        for s in sensors:
            if s.get("sensorTypeId") == 2: # 控制类设备
                name = s.get("sensorName")
                state = (s.get("value") == "1")
                # Streamlit toggle 按钮
                toggled = st.toggle(f"🔌 {name}", value=state, key=f"sw_{s.get('id')}")
                
                # 【需求11】联动农事绑定 (核心逻辑体现)
                if toggled and not state: # 刚被打开
                    if "雾化" in name:
                        with st.expander("📝 记录：降温加湿工单 (系统检测到雾化开启)", expanded=True):
                            st.text_input("操作员", "admin")
                            st.number_input("预计开启时长(分钟)", min_value=1, value=30)
                            st.button("提交记录", key=f"btn_{s.get('id')}")
                    elif "卷被" in name or "卷膜" in name:
                        with st.expander("📝 记录：通风保温工单 (系统检测到卷膜动作)", expanded=True):
                            st.selectbox("操作意图", ["早晨见光", "夜间保温", "强风收拢"])
                            st.button("提交记录", key=f"btn_{s.get('id')}")


# ----------------- 页面三：多维数据分析 -----------------
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
                    
                    # 智能提取基础指标（去掉“1号”、“2组”等前缀）
                    if "号" in name:
                        base_metrics.add(name.split("号")[-1])
                    elif "组" in name:
                        base_metrics.add(name.split("组")[-1])
                    else:
                        base_metrics.add(name)
                        
    metric_opts = sorted(list(valid_metrics))
    base_metric_opts = sorted(list(base_metrics))
    
    if not metric_opts:
        st.warning("⚠️ 当前没有任何有效的环境传感器数据可供分析。")
        st.stop()
        
    # ================= 2. 渲染三大分析模块 =================
    tab1, tab2, tab3 = st.tabs(["📊 参数相关性分析 (组合图表)", "📉 前中后区域聚合", "📥 历史数据导出"])
    
    with tab1:
        # ---------------- 【需求3】参数相关性分析 ----------------
        st.subheader("参数相关性分析 (自动寻优)")
        st.markdown("通过对比各棚的 **自变量** 与 **因变量**，寻找最佳生长环境参数组合。")
        
        c1, c2 = st.columns(2)
        x_metric = c1.selectbox("横坐标 (X轴) - 例如光照、土壤EC", metric_opts, index=0)
        y_metric = c2.selectbox("纵坐标 (Y轴) - 例如温度、酸碱度", metric_opts, index=1 if len(metric_opts) > 1 else 0)
        if x_metric == y_metric:
            st.warning("⚠️ 横坐标与纵坐标选择了相同的指标，请选择两个【不同】的参数进行相关性对比。")
        else:
            # 只有当两个指标不同时，才去遍历数据和画图
            corr_data = []
            for d in st.session_state.device_data:
                gh_name = d.get("deviceName", "未知")
                sensors = d.get('sensorsList', [])
                # 精确查找 X 和 Y 对应传感器的值
                x_sensor = next((s for s in sensors if s.get("sensorName") == x_metric), None)
                y_sensor = next((s for s in sensors if s.get("sensorName") == y_metric), None)
                
                if x_sensor and y_sensor:
                    try:
                        corr_data.append({
                            "温室": gh_name, 
                            x_metric: float(x_sensor.get("value")), 
                            y_metric: float(y_sensor.get("value"))
                        })
                    except:
                        continue # 容错处理
                    
            df_corr = pd.DataFrame(corr_data)
            if not df_corr.empty:
                # 绘制散点图并加上 OLS 线性回归趋势线
                fig_scatter = px.scatter(
                    df_corr, x=x_metric, y=y_metric, hover_name="温室", 
                    trendline="ols", color="温室", size_max=15,
                    title=f"各棚【{x_metric}】对【{y_metric}】的相关性影响"
                )
                fig_scatter.update_traces(marker=dict(size=12))
                st.plotly_chart(fig_scatter, use_container_width=True)
                
                # 相关性
                # 计算皮尔逊相关系数
                r_value = df_corr[x_metric].corr(df_corr[y_metric])
                
                if pd.isna(r_value):
                    analysis_text = "数据点方差不足，无法计算有效相关性。"
                else:
                    # 将数学系数转化为大白话农业解读
                    if r_value > 0.7:
                        insight = "呈现 **强正相关** 📈。这意味着随着数值上升，目标指标会呈显著上升趋势。在农事操作中，可以通过提升前者来有效拉高后者。"
                    elif r_value > 0.3:
                        insight = "呈现 **弱至中度正相关** ↗️。两者有一定正向关联，但可能还受到其他环境因素的干扰。"
                    elif r_value > -0.3:
                        insight = "呈现 **无明显线性相关** ➖。说明这两个参数之间在当前状态下没有直接的因果或联动关系。"
                    elif r_value > -0.7:
                        insight = "呈现 **中度负相关** ↘️。两者有一定反向制约关系，一个上升时，另一个倾向于下降。"
                    else:
                        insight = "呈现 **强负相关** 📉。两者之间存在明显的拮抗效应。"
                
                # 使用带颜色的状态框展示分析结论
                st.info(f"💡 **系统智能分析诊断**：\n\n经计算，当前【{x_metric}】与【{y_metric}】的相关系数(r)为 **{r_value:.2f}**，{insight}")
            else:
                st.info(f"暂无法在各棚中同时匹配到有效的【{x_metric}】和【{y_metric}】数据。")
        # corr_data = []
        # for d in st.session_state.device_data:
        #     gh_name = d.get("deviceName", "未知")
        #     sensors = d.get('sensorsList', [])
            
        #     # 精确查找 X 和 Y 对应传感器的值
        #     x_sensor = next((s for s in sensors if s.get("sensorName") == x_metric), None)
        #     y_sensor = next((s for s in sensors if s.get("sensorName") == y_metric), None)
            
        #     if x_sensor and y_sensor:
        #         try:
        #             corr_data.append({
        #                 "温室": gh_name, 
        #                 x_metric: float(x_sensor.get("value")), 
        #                 y_metric: float(y_sensor.get("value"))
        #             })
        #         except:
        #             continue # 容错处理
                
        # df_corr = pd.DataFrame(corr_data)
        # if not df_corr.empty:
        #     # 绘制散点图并加上 OLS 线性回归趋势线
        #     fig_scatter = px.scatter(
        #         df_corr, x=x_metric, y=y_metric, hover_name="温室", 
        #         trendline="ols", color="温室", size_max=15,
        #         title=f"各棚【{x_metric}】对【{y_metric}】的相关性影响"
        #     )
        #     fig_scatter.update_traces(marker=dict(size=12))
        #     st.plotly_chart(fig_scatter, use_container_width=True)
        # else:
        #     st.info(f"暂无法在各棚中同时匹配到有效的【{x_metric}】和【{y_metric}】数据。")
            
    with tab2:
        # ---------------- 【需求3】前中后区域聚合分析 ----------------
        st.subheader("大棚微气候区域温差分析 (前/中/后)")
        st.markdown("由于通风和光照差异，大棚两端与中间通常存在微气候差异。此图表进行区域对比。")
        
        # 让用户选择基础指标（比如“空温”或“土壤湿度”）
        agg_base = st.selectbox("请选择要聚合的指标基类", base_metric_opts)
        
        agg_data = []
        for d in st.session_state.device_data:
            gh = d.get("deviceName")
            sensors = d.get('sensorsList', [])
            
            # 动态组合寻找前中后的名字（支持 "号" 和 "组"）
            front_val = None
            mid_val = None
            back_val = None
            
            for s in sensors:
                name = s.get("sensorName", "")
                val_str = str(s.get("value", "0"))
                if val_str in ['0', '0.0']: continue
                
                try:
                    if agg_base in name:
                        if "1号" in name or "1组" in name: front_val = float(val_str)
                        if "2号" in name or "2组" in name: mid_val = float(val_str)
                        if "3号" in name or "3组" in name: back_val = float(val_str)
                except:
                    pass
            
            # 存入聚合列表
            if front_val is not None: agg_data.append({"温室": gh, "区域": "前区(1号/1组)", "数值": front_val})
            if mid_val is not None: agg_data.append({"温室": gh, "区域": "中区(2号/2组)", "数值": mid_val})
            if back_val is not None: agg_data.append({"温室": gh, "区域": "后区(3号/3组)", "数值": back_val})
            
        df_agg = pd.DataFrame(agg_data)
        if not df_agg.empty:
            # 绘制分组柱状图
            fig_agg = px.bar(
                df_agg, x="温室", y="数值", color="区域", 
                barmode="group", text_auto=True,
                title=f"各棚【{agg_base}】前中后区域分布"
            )
            fig_agg.update_layout(yaxis_title=f"{agg_base} 数值")
            st.plotly_chart(fig_agg, use_container_width=True)
        else:
            st.info(f"未能在设备中检测到区分前中后的【{agg_base}】数据。")
            
    with tab3:
        # ---------------- 【需求3】自定义时段与历史数据导出 ----------------
        st.subheader("自定义时段与历史数据导出")
        st.caption("从 SQLite 数据库提取精准的历史时序快照，一键导出为 Excel 可读格式。")
        
        col_ex1, col_ex2, col_ex3 = st.columns(3)
        # 1. 选大棚
        device_names = [d['deviceName'] for d in st.session_state.device_data]
        export_gh = col_ex1.selectbox("步骤一：选择大棚", device_names)
        
        # 2. 选具体的传感器 (联动上方的动态选项)
        export_sensor_name = col_ex2.selectbox("步骤二：选择要导出的指标", metric_opts)
        
        # 3. 自定义时间段
        date_range = col_ex3.date_input("步骤三：选择时间范围", 
                                        value=(datetime.now() - timedelta(days=1), datetime.now()))
        
        if len(date_range) == 2:
            start_date, end_date = date_range
            # 格式化为数据库所需的字符串时间格式
            start_str = start_date.strftime("%Y-%m-%d 00:00:00")
            end_str = end_date.strftime("%Y-%m-%d 23:59:59")
            
            if st.button("🔍 查询历史数据并准备导出", type="primary"):
                with st.spinner("正在从本地数据库检索..."):
                    import database_manager
                    
                    # 反查出目标大棚下该传感器的专属 ID
                    target_device = next((d for d in st.session_state.device_data if d['deviceName'] == export_gh), None)
                    target_sensor = next((s for s in target_device.get('sensorsList', []) if s.get("sensorName") == export_sensor_name), None)
                    
                    if not target_sensor:
                        st.error(f"大棚 {export_gh} 下未找到指标：{export_sensor_name}")
                    else:
                        sensor_id = target_sensor.get("id")
                        unit = target_sensor.get("unit", "")
                        
                        # 调用我们写的查询接口
                        history_rows = database_manager.get_sensor_history(sensor_id, start_str, end_str)
                        if not history_rows:
                            st.warning(f"数据库中未找到 {start_str} 至 {end_str} 期间的数据。")
                        else:
                            df_export = pd.DataFrame(history_rows)
                            # 清洗并美化数据表头
                            df_export = df_export.rename(columns={
                                "add_time": "采集时间", 
                                "val": f"{export_sensor_name}数值 ({unit})",
                                "switcher": "开关状态"
                            })
                            
                            st.success(f"✅ 成功提取到 {len(df_export)} 条历史记录！")
                            st.dataframe(df_export, height=250)
                            
                            # 转换为 CSV 以下载
                            csv_data = df_export.to_csv(index=False).encode('utf-8-sig') # utf-8-sig 兼容 Excel
                            st.download_button(
                                label="📥 点击下载至本地 (CSV)",
                                data=csv_data,
                                file_name=f"{export_gh}_{export_sensor_name}_历史数据.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
        else:
            st.info("请选择一个完整的起止日期范围。")

# ----------------- 页面四：批次工单与联控 -----------------
elif menu == "📋 批次工单与联控 (抓生产)":
    st.header("📋 批量生产与批次管理")
    
    col1, col2 = st.columns(2, gap="large")
    with col1:
        # ================= 【需求6】多设备联控 =================
        st.subheader("🚀 多设备一键联控")
        st.caption("勾选多个目标，系统将自动识别可控硬件并并发下发指令。")
        
        # 1. 提取真实在线的设备名称
        online_devices = [d['deviceName'] for d in st.session_state.device_data if d.get('isLine') == 1]
        
        if not online_devices:
            st.error("当前无在线设备可控！")
        else:
            target_ghs = st.multiselect("1. 勾选需要联控的在线温室", online_devices, default=online_devices[0:1] if online_devices else None)
            
            # 2. 【核心逻辑】动态提取选定大棚下的控制类设备名称 (sensorTypeId 为 2, 5, 6)
            switch_names = set()
            for d in st.session_state.device_data:
                if d.get('deviceName') in target_ghs:
                    sensors = d.get('sensorsList') or []
                    for s in sensors:
                        # 只筛选控制类型传感器
                        if s.get('sensorTypeId') in [2, 5, 6]:
                            name = s.get("sensorName")
                            if name:
                                switch_names.add(name)
            
            # 3. 动态组装下拉菜单选项
            action_options = []
            if switch_names:
                for name in sorted(list(switch_names)):
                    action_options.append(f"🟢 打开所有 {name}")
                    action_options.append(f"🔴 关闭所有 {name}")
            else:
                action_options = ["⚠️ 选中的大棚暂无可控设备"]
                
            # 4. 渲染动态选项
            action = st.selectbox("2. 自动识别并选择统一执行的动作", action_options)
            
            # 5. 执行下发
            if st.button("🚀 下发联控指令", type="primary", use_container_width=True):
                if not target_ghs:
                    st.warning("请至少选择一个温室！")
                elif "⚠️" in action:
                    st.error("当前无有效指令可下发。")
                else:
                    # 【真实联控逻辑占位】：你需要遍历 target_ghs，调用 IotClient 去依次下发
                    st.success(f"✅ 指令已成功发送至 {len(target_ghs)} 座大棚的消息队列！")
                    st.json({
                        "目标群组": target_ghs, 
                        "执行指令": action, 
                        "状态": "队列排队中..."
                    })
    with col2:
        # ================= 【需求9】电子工单模板 =================
        st.subheader("📑 标准化电子工单")
        with st.container(border=True):
            task_type = st.selectbox("作业类型 (SOP)", ["🌱 播种与定植", "💧 智能灌溉", "💊 水肥一体化施肥", "✂️ 打叶与采收"])
            operator = st.text_area("操作负责人", placeholder="例如：张农技师")
            st.text_area("作业内容标准与指导记录", placeholder="例如：今日执行生菜A区定植，营养液EC目标调至1.8...")
            if st.button("💾 生成并归档工单"):
                st.toast("工单已归档至数据库！")
                
            # TODO 此时的数据需要和数据库联动进行保存，并且在后续的工单管理模块中可以查询和追踪。
        
    st.divider()
    
    # ================= 【需求10】批次管理与生长节点 =================
    st.subheader("📦 农作物批次与生长曲线关联")
    st.caption("将环境数据直接绑定到具体的种植批次上。")
    
    c_b1, c_b2 = st.columns([1, 3])
    with c_b1:
        batch_no = st.selectbox("选择追踪批次", ["🍅 番茄批次-202604", "🥬 生菜批次-202605"])
        st.metric("批次运行时长", "34 天")
        st.metric("预计采收倒计时", "12 天")
        
    with c_b2:
        # 使用进度条和步进图模拟生长节点
        st.markdown("#### 当前阶段：开花坐果期 (阶段 3/4)")
        st.progress(75, text="自动环境策略：已根据生长期自动下调夜间温度目标以促进干物质积累。")
        
        # 日均温变化曲线 由数据集中读取处理
        dates = pd.date_range(start="2026-04-01", periods=34).strftime("%m-%d")
        import numpy as np
        temps = 20 + np.random.randn(34).cumsum() # 生成平滑的随机曲线
        
        fig_batch = px.line(x=dates, y=temps, title=f"{batch_no} 历史日均温曲线", labels={"x": "日期", "y": "日均温 (℃)"})
        fig_batch.update_layout(height=250, margin={"t":30, "b":0})
        st.plotly_chart(fig_batch, use_container_width=True)
        

# ----------------- 页面五：策略与预警 -----------------
elif menu == "⚙️ 策略与预警 (设规则)":
    st.header("⚙️ 自动化策略与报警配置")
    
    # 【需求8】阈值报警及短信微信
    st.subheader("报警规则设定")
    with st.form("alert_settings"):
        st.selectbox("应用范围", ["全局所有大棚", "单独指定大棚"])
        c1, c2 = st.columns(2)
        c1.number_input("温度上限报警阈值 (°C)", value=35)
        c2.number_input("温度下限报警阈值 (°C)", value=10)
        
        st.markdown("**推送接收人设置**")
        st.checkbox("开启短信推送")
        st.text_input("接收手机号", "13800000000")
        st.checkbox("开启微信公众号/企业微信推送")
        
        if st.form_submit_button("保存配置"):
            st.toast("预警规则保存成功！")
