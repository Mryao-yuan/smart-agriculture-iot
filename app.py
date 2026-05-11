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
# import database_manager 
import db_manager


from utils.weather import init_weather_alert_config,get_weather_alert
from utils.login import check_password
from utils.text_operate import extract_gh_num,get_sorted_devices,parse_zone,process_history_records
from utils.alter import user_webhook_check
from utils.style import load_local_css,generate_sensor_card_html
from utils.controllers import DEBUG_MODE, handle_toggle_change, execute_batch_control
from utils.iot_client import IotClient
from utils.page import get_device_status_meta, sensor_display_value, sensor_pretty_name, sensor_accent_color, save_binding_work_order, render_greenhouse_selector_cards, render_binding_form, render_greenhouse_sandbox, get_cached_weather
from utils.timezone import get_local_now
from datetime import datetime



bg_path = "imgs/bg1.png"
json_path="./users.json"

# === login ===
if not check_password(bg_path,json_path):
    st.stop()

# ==================== 1. 基础配置与全局工具 ====================
st.set_page_config(page_title="智慧温室 IoT 平台", layout="wide", page_icon="🌿")

# ==================== 2. Session 状态初始化 ====================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'device_data' not in st.session_state:
    st.session_state.device_data = [] # 存放拉取的真实设备数据
if 'menu_target' not in st.session_state:
    st.session_state.menu_target = "🌐 设备整体状态"
if 'device_data_loaded' not in st.session_state:
    st.session_state.device_data_loaded = False

# ==================== 3. 侧边栏导航 ====================
with st.sidebar:
    st.title("🌿 智慧温室 IoT 平台")
    # 页面路由菜单
    menu_options = [
        "🌐 设备整体状态", 
        "🎮 单棚设备沙盘",
        "📈 多维数据分析", 
        "📋 批次工单与联控",
        "⚙️ 策略与预警"
    ]
    default_menu = st.session_state.get("menu_target", "🌐 设备整体状态")
    if default_menu not in menu_options:
        default_menu = "🌐 设备整体状态"
    menu = st.radio("🏠 业务导航", menu_options, index=menu_options.index(default_menu))
    st.session_state["menu_target"] = menu
    if not st.session_state.device_data_loaded:
        with st.spinner("正在加载设备数据..."):
            data = device_info_get()
            st.session_state.device_data = (data or {}).get("dataList", []) or []
            st.session_state.device_data_loaded = True
    if st.button("🔄 刷新设备数据", use_container_width=True):
        with st.spinner("正在刷新设备数据..."):
            device_info_get.clear()
            data = device_info_get()
            st.session_state.device_data = (data or {}).get("dataList", []) or []
            st.session_state.device_data_loaded = True
        st.rerun()

# ----------------- 页面一：全局驾驶舱 -----------------
if menu == "🌐 设备整体状态":
    st.header("设备情况")
    init_weather_alert_config()
    config = st.session_state.weather_alert_config

    if "selected_greenhouse" not in st.session_state:
        st.session_state["selected_greenhouse"] = None
    if "pending_control_binding" not in st.session_state:
        st.session_state["pending_control_binding"] = None
    # 获取天气信息
    if st.session_state.device_data:
        first_device = st.session_state.device_data[0]
        lat = first_device.get('lat')
        lng = first_device.get('lng')
        weather_info = get_cached_weather(lat, lng, WEATHER_API_KEY)
        if weather_info:
            alert_level, alert_msg = get_weather_alert(weather_info, config)
            city = weather_info.get('location', '未知地区').split('省')[-1]
            weather = weather_info.get('weather', '未知')
            temp = weather_info.get('temperature', '--')
            humidity = weather_info.get('humidity', '--')
            wind_power = weather_info.get('wind_power', '--')
            banner_text = f"🌤️ {city} 当前天气：{weather} | 温度 {temp}℃ 湿度 {humidity}% 风力 {wind_power}级"
            if alert_level == "error":
                st.error(f"{banner_text} | 🚨 **报警**：{alert_msg}")
            elif alert_level == "warning":
                st.warning(f"{banner_text} | ⚠️ **注意**：{alert_msg}")
            else:
                st.info(f"{banner_text} | ✅ 暂无天气预警信息")

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
                new_enable = st.checkbox("启用天气预警", value=config['enable_alerts'])
            submit_btn = st.form_submit_button("💾 保存配置", type="primary", width='stretch')
            if submit_btn:
                st.session_state.weather_alert_config.update({
                    'temp_high': new_temp_high,
                    'temp_low': new_temp_low,
                    'wind_power': new_wind,
                    'humidity_high': new_hum_high,
                    'humidity_low': new_hum_low,
                    'enable_alerts': new_enable
                })
                st.toast("✅ 天气预警规则已保存！")
                st.rerun()

    if st.session_state.device_data:
        render_greenhouse_selector_cards(st.session_state.device_data)
        sorted_device_names = sorted([d['deviceName'] for d in st.session_state.device_data], key=extract_gh_num)
        if st.session_state.get("selected_greenhouse") not in sorted_device_names:
            st.session_state["selected_greenhouse"] = sorted_device_names[0]
        current_gh = st.session_state["selected_greenhouse"]
    else:
        st.info("暂无设备坐标数据")

    active_batch_labels = []
    batch_lookup = {}
    if st.session_state.device_data:
        try:
            conn = db_manager.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT batch_id, gh_name, crop_name, variety
                    FROM batches
                    WHERE status = 1
                    ORDER BY start_time DESC
                """)
                active_batches_data = cursor.fetchall()
            conn.close()
            active_batch_labels = [
                f"ID:{b['batch_id']} | {b['gh_name']} - {b['crop_name']} ({(b.get('variety') or '未填写品种').strip()})"
                for b in active_batches_data
            ]
            batch_lookup = {label: batch for label, batch in zip(active_batch_labels, active_batches_data)}
        except Exception as e:
            st.warning(f"联动工单批次加载失败: {e}")

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
            time_range = st.selectbox(
                "🕒 时间范围",
                ["当前1小时", "今日", "最近一周", "最近一月"],
                index=1
            )
        now = get_local_now()
        if time_range == "当前1小时":
            start_time = now - timedelta(hours=1)
        elif time_range == "今日":
            start_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "最近一周":
            start_time = now - timedelta(days=7)
        else:
            start_time = now - timedelta(days=30)

        st.caption(f"📅 统计范围：{start_time.strftime('%Y-%m-%d %H:%M:%S')} 至 现在")
        line_chart_data = []
        with st.spinner("正在从数据库拉取历史时序数据..."):
            import database_manager
            import db_manager
            for d in st.session_state.device_data:
                gh_name = d.get("deviceName", "未知大棚")
                sensors_list = d.get('sensorsList') or []
                target_sensor = next((s for s in sensors_list if s.get("sensorName") == selected_metric), None)
                if target_sensor:
                    sensor_id = target_sensor.get("id")
                    history_records = db_manager.get_sensor_history_tidb(sensor_id, start_time, now)
                    for record in history_records:
                        line_chart_data.append({
                            "温室名称": gh_name,
                            "采集时间": record["add_time"],
                            "数值": float(record["value"]),
                            "单位": target_sensor.get("unit")
                        })
        if line_chart_data:
            df_plot = pd.DataFrame(line_chart_data)
            df_plot["采集时间"] = pd.to_datetime(df_plot["采集时间"])
            df_plot["数值"] = pd.to_numeric(df_plot["数值"], errors='coerce')
            unit_str = line_chart_data[0].get("单位", "")
            now = get_local_now()
            actual_min_date = df_plot["采集时间"].min().date()
            actual_max_date = df_plot["采集时间"].max().date()
            date_span = (actual_max_date - actual_min_date).days
            days_map = {"最近一周": 7, "最近一月": 30}
            if time_range in days_map:
                theory_start = (now - timedelta(days=days_map[time_range])).date()
                if actual_min_date > theory_start:
                    st.info(f"💡 数据库最早记录为 **{actual_min_date}**，已为您展示至今趋势。")
                if date_span < 1:
                    sample_rule = '1h'
                    x_col = "采集时间"
                    is_category = False
                    axis_format = "%m-%d %H:%M"
                else:
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
                if time_range == "今日":
                    final_df_list = []
                    for gh in df_plot["温室名称"].unique():
                        gh_df = df_plot[df_plot["温室名称"] == gh].set_index("采集时间")
                        hourly_df = gh_df["数值"].resample("1h").mean().reset_index()
                        hourly_df["温室名称"] = gh
                        final_df_list.append(hourly_df)
                    df_curve = pd.concat(final_df_list).dropna(subset=["数值"])
                    df_curve = df_curve.sort_values("采集时间")
                    x_col = "采集时间"
                    is_category = False
                    axis_format = "%H:%M"
                else:
                    df_curve = df_plot.copy().sort_values("采集时间")
                    x_col = "采集时间"
                    is_category = False
                    axis_format = "%H:%M"

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

        render_binding_form(active_batch_labels, batch_lookup)

# ----------------- 页面二：单棚设备沙盘 -----------------
elif menu == "🎮 单棚设备沙盘":
    st.header("🎮 单棚设备沙盘")
    st.caption("查看单个温室的设备沙盘、实时数据和控制面板。")

    if not st.session_state.device_data:
        st.info("暂无设备数据，请先同步设备台账。")
    else:
        if "selected_greenhouse" not in st.session_state or st.session_state["selected_greenhouse"] is None:
            sorted_device_names = sorted([d['deviceName'] for d in st.session_state.device_data], key=extract_gh_num)
            st.session_state["selected_greenhouse"] = sorted_device_names[0]

        sorted_device_names = sorted([d['deviceName'] for d in st.session_state.device_data], key=extract_gh_num)
        if st.session_state["selected_greenhouse"] not in sorted_device_names:
            st.session_state["selected_greenhouse"] = sorted_device_names[0]

        top_cols = st.columns([2, 1])
        with top_cols[0]:
            selected_gh = st.selectbox(
                "🏠 选择目标温室",
                sorted_device_names,
                index=sorted_device_names.index(st.session_state["selected_greenhouse"]),
                key="sandbox_page_selected_gh"
            )
            st.session_state["selected_greenhouse"] = selected_gh
        with top_cols[1]:
            if st.button("⬅️ 返回地图总览", use_container_width=True, key="back_to_dashboard"):
                st.session_state["menu_target"] = "🌐 设备整体状态"
                st.rerun()

        target_device = next(d for d in st.session_state.device_data if d['deviceName'] == st.session_state["selected_greenhouse"])
        render_greenhouse_sandbox(target_device)

        active_batch_labels = []
        batch_lookup = {}
        try:
            conn = db_manager.get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT batch_id, gh_name, crop_name, variety
                    FROM batches
                    WHERE status = 1
                    ORDER BY start_time DESC
                """)
                active_batches_data = cursor.fetchall()
            conn.close()
            active_batch_labels = [
                f"ID:{b['batch_id']} | {b['gh_name']} - {b['crop_name']} ({(b.get('variety') or '未填写品种').strip()})"
                for b in active_batches_data
            ]
            batch_lookup = {label: batch for label, batch in zip(active_batch_labels, active_batches_data)}
        except Exception as e:
            st.warning(f"联动工单批次加载失败: {e}")

        render_binding_form(active_batch_labels, batch_lookup)

# ----------------- 页面三：多维数据分析 -----------------
elif menu == "📈 多维数据分析":
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

    now = get_local_now()
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
                                scatter_kwargs = {
                                    "data_frame": df_corr,
                                    "x": x_metric,
                                    "y": y_metric,
                                    "hover_name": "采集时间",
                                    "color_discrete_sequence": ["#1f77b4"],
                                    "title": f"【{selected_gh}】历史相关性：{x_metric} vs {y_metric}",
                                }
                                try:
                                    import statsmodels.api as sm  # noqa: F401
                                    scatter_kwargs["trendline"] = "lowess"
                                except ModuleNotFoundError:
                                    st.info("💡 当前运行环境未安装 `statsmodels`，已跳过 LOWESS 趋势线，仅展示散点相关性。")

                                fig_scatter = px.scatter(**scatter_kwargs)
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
            value=(get_local_now() - timedelta(days=1), get_local_now())
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
elif menu == "📋 批次工单与联控":
    db_manager.init_db()
    st.header("📋 批次工单与联控")
    st.caption("围绕种植批次、标准工单和多棚联控形成可追溯的生产闭环。")

    stage_options = ["播种期", "出苗期/缓苗期", "生长期/莲座期", "结球期/挂果期", "采收期"]
    task_options = ["🌱 播种与定植", "💧 智能灌溉", "💊 水肥一体化施肥", "✂️ 打叶与采收", "🌀 强制通风", "🤖 联控执行"]
    bucket_options = {"1小时": "1h", "6小时": "6h", "1天": "1d"}

    def normalize_dt(value):
        if value in (None, "", "None"):
            return None
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return pd.to_datetime(value).to_pydatetime()

    def normalize_work_order_finish_time(value):
        return normalize_dt(value)

    def format_date(value, with_time=False):
        dt_value = normalize_dt(value)
        if not dt_value:
            return "未设置"
        return dt_value.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")

    def as_date_input_value(value, fallback=None):
        dt_value = normalize_dt(value)
        if dt_value:
            return dt_value.date()
        return fallback or get_local_now().date()

    def format_duration_value(duration_mins):
        if duration_mins in (None, "", "None"):
            return "-"
        try:
            if pd.isna(duration_mins):
                return "-"
        except Exception:
            pass
        return str(int(duration_mins))

    def get_work_order_time_window(order):
        finish_time = normalize_work_order_finish_time(order.get("created_at"))
        duration_text = format_duration_value(order.get("duration_mins"))
        if duration_text == "-":
            return finish_time, None
        duration_mins = int(duration_text)
        start_time = finish_time - timedelta(minutes=duration_mins) if finish_time else None
        return start_time, finish_time

    def format_batch_label(batch):
        variety = (batch.get("variety") or "未填写品种").strip()
        return f"ID:{batch['batch_id']} | {batch['gh_name']} - {batch['crop_name']} ({variety})"

    def stage_index(stage_name):
        if stage_name in stage_options:
            return stage_options.index(stage_name)
        return 0

    def apply_growth_stage_overlay(fig, crop_name, start_date, end_date):
        runtime_days = max(0, (end_date - start_date).days)

        def add_stage_band(x0, x1, color, text, opacity=0.1):
            band_end = min(x1, end_date)
            if band_end <= x0:
                return
            fig.add_vrect(
                x0=x0,
                x1=band_end,
                fillcolor=color,
                opacity=opacity,
                line_width=0,
                annotation_text=text
            )

        if "生菜" in crop_name:
            add_stage_band(start_date, start_date + timedelta(days=7), "green", "🌱 缓苗期")
            add_stage_band(start_date + timedelta(days=7), start_date + timedelta(days=25), "yellow", "🌿 莲座期")
            add_stage_band(start_date + timedelta(days=25), end_date, "orange", "🥬 结球期")
        elif "番茄" in crop_name:
            add_stage_band(start_date, start_date + timedelta(days=15), "green", "🌱 苗期")
            add_stage_band(start_date + timedelta(days=15), start_date + timedelta(days=40), "yellow", "🌼 开花坐果期")
            add_stage_band(start_date + timedelta(days=40), end_date, "red", "🍅 结果膨大期", opacity=0.05)
        else:
            add_stage_band(start_date, end_date, "blue", f"📊 生长期 ({runtime_days}天)", opacity=0.05)

    def load_batch_page_data():
        conn = db_manager.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        b.*,
                        COALESCE(w.order_count, 0) AS work_order_count,
                        w.last_work_order_at
                    FROM batches b
                    LEFT JOIN (
                        SELECT
                            batch_id,
                            COUNT(*) AS order_count,
                            MAX(created_at) AS last_work_order_at
                        FROM work_orders
                        GROUP BY batch_id
                    ) w ON w.batch_id = b.batch_id
                    ORDER BY b.status DESC, b.start_time DESC
                """)
                batches = cursor.fetchall()
                cursor.execute("""
                    SELECT
                        w.*,
                        b.crop_name,
                        b.variety,
                        b.current_stage
                    FROM work_orders w
                    LEFT JOIN batches b ON b.batch_id = w.batch_id
                    ORDER BY w.created_at DESC
                    LIMIT 500
                """)
                orders = cursor.fetchall()
            return batches, orders
        finally:
            conn.close()

    def load_greenhouse_sensor_options(gh_name):
        conn = db_manager.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT
                        s.sensor_name,
                        COALESCE(s.unit, '') AS unit
                    FROM sensors s
                    JOIN devices d ON s.device_id = d.device_id
                    WHERE d.gh_name = %s
                      AND s.sensor_type_id = 1
                      AND COALESCE(s.is_delete, 0) = 0
                    ORDER BY
                        CASE
                            WHEN s.sensor_name LIKE '%%温度%%' OR s.sensor_name LIKE '%%空温%%' THEN 0
                            WHEN s.sensor_name LIKE '%%湿度%%' THEN 1
                            ELSE 2
                        END,
                        s.sensor_name
                """, (gh_name,))
                return cursor.fetchall()
        finally:
            conn.close()

    def load_batch_history(gh_name, sensor_name, start_time, bucket_rule):
        conn = db_manager.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT sh.add_time, sh.value
                    FROM sensor_history sh
                    JOIN sensors s ON sh.sensor_id = s.sensor_id
                    JOIN devices d ON s.device_id = d.device_id
                    WHERE d.gh_name = %s
                      AND s.sensor_name = %s
                      AND sh.add_time >= %s
                    ORDER BY sh.add_time ASC
                """, (gh_name, sensor_name, start_time))
                rows = cursor.fetchall()
        finally:
            conn.close()

        if not rows:
            return pd.DataFrame()

        df_history = pd.DataFrame(rows)
        df_history["value"] = pd.to_numeric(df_history["value"], errors="coerce")
        df_history["add_time"] = pd.to_datetime(df_history["add_time"])
        df_history = df_history.dropna(subset=["value"])
        if df_history.empty:
            return df_history

        df_history["bucket_time"] = df_history["add_time"].dt.floor(bucket_rule)
        return df_history.groupby("bucket_time", as_index=False)["value"].mean()

    def save_work_order_records(records):
        if not records:
            return 0
        finish_time = get_local_now().replace(microsecond=0)
        records_with_finish_time = [tuple(record) + (finish_time,) for record in records]
        conn = db_manager.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.executemany("""
                    INSERT INTO work_orders (batch_id, gh_name, task_type, operator, content, duration_mins, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, records_with_finish_time)
            conn.commit()
            return len(records)
        finally:
            conn.close()

    def delete_batch_with_orders(batch_id, delete_orders=False):
        conn = db_manager.get_connection()
        try:
            with conn.cursor() as cursor:
                if delete_orders:
                    cursor.execute("DELETE FROM work_orders WHERE batch_id = %s", (batch_id,))
                cursor.execute("DELETE FROM batches WHERE batch_id = %s", (batch_id,))
            conn.commit()
        finally:
            conn.close()

    def delete_work_order(order_id):
        conn = db_manager.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM work_orders WHERE id = %s", (order_id,))
            conn.commit()
        finally:
            conn.close()

    def bulk_delete_test_data(delete_finished_batches=False, delete_all_orders=False):
        conn = db_manager.get_connection()
        try:
            with conn.cursor() as cursor:
                if delete_all_orders:
                    cursor.execute("DELETE FROM work_orders")
                if delete_finished_batches:
                    cursor.execute("DELETE FROM work_orders WHERE batch_id IN (SELECT batch_id FROM batches WHERE status = 0)")
                    cursor.execute("DELETE FROM batches WHERE status = 0")
            conn.commit()
        finally:
            conn.close()

    def archive_control_orders(target_ghs, action_label, operator_name, note_text, details_log, running_batches):
        archive_records = []
        archived_ghs = []
        for batch in running_batches:
            gh_name = batch["gh_name"]
            if gh_name not in target_ghs:
                continue
            gh_logs = [
                f"{row.get('对象', '未知对象')} {row.get('动作', '')} -> {row.get('执行结果', '')}"
                for row in details_log
                if row.get("大棚") == gh_name
            ]
            if not gh_logs:
                continue
            content_parts = [
                f"联控动作：{action_label}",
                f"目标温室：{gh_name}",
                f"附加说明：{note_text or '无'}",
                "执行明细：",
                *gh_logs[:20]
            ]
            if len(gh_logs) > 20:
                content_parts.append(f"... 其余 {len(gh_logs) - 20} 条请查看联控执行面板")
            archive_records.append((
                batch["batch_id"],
                gh_name,
                "🤖 联控执行",
                operator_name or "系统联控",
                "\n".join(content_parts),
                None
            ))
            archived_ghs.append(gh_name)
        save_work_order_records(archive_records)
        skipped_ghs = [gh for gh in target_ghs if gh not in archived_ghs]
        return len(archive_records), skipped_ghs

    def ensure_api_client():
        if DEBUG_MODE:
            return st.session_state.get("api_client"), None
        cached_client = st.session_state.get("api_client")
        if cached_client is not None:
            return cached_client, None
        try:
            client = IotClient()
            login_res = client.login(USERNAME, PASSWORD, API_KEY)
            if login_res.get("flag") != "00":
                return None, "云端平台登录失败。"
            token_res = client.get_access_token(USERNAME, PASSWORD)
            if token_res.get("flag") != "00":
                return None, "获取访问令牌失败。"
            st.session_state["api_client"] = client
            return client, None
        except Exception as e:
            return None, f"客户端初始化发生异常: {e}"

    device_names = sorted({d.get("deviceName", "未知") for d in st.session_state.device_data if d.get("deviceName")})
    online_devices = sorted({d.get("deviceName", "未知") for d in st.session_state.device_data if d.get("isLine") == 1 and d.get("deviceName")})

    try:
        all_batches, recent_work_orders = load_batch_page_data()
    except Exception as e:
        st.error(f"批次页面初始化失败: {e}")
        st.stop()

    active_batches = [b for b in all_batches if b.get("status") == 1]
    batch_lookup = {format_batch_label(batch): batch for batch in all_batches}
    active_batch_labels = [format_batch_label(batch) for batch in active_batches]
    today = get_local_now().date()
    due_soon_count = 0
    overdue_count = 0

    for batch in active_batches:
        harvest_dt = normalize_dt(batch.get("expected_harvest"))
        if not harvest_dt:
            continue
        days_left = (harvest_dt.date() - today).days
        if days_left < 0:
            overdue_count += 1
        elif days_left <= 7:
            due_soon_count += 1

    today_order_count = 0
    for order in recent_work_orders:
        start_time, _ = get_work_order_time_window(order)
        if start_time and start_time.date() == today:
            today_order_count += 1

    overview_tab, create_tab, order_tab, control_tab = st.tabs([
        "📋 批次概览",
        "➕ 新增批次",
        "📑 工单中心",
        "🚀 联控执行"
    ])

    with overview_tab:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("运行中批次", f"{len(active_batches)} 个")
        m2.metric("7天内到期", f"{due_soon_count} 个")
        m3.metric("已逾期未结束", f"{overdue_count} 个")
        m4.metric("今日新增工单", f"{today_order_count} 条")

        filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1.4])
        status_filter = filter_col1.selectbox("状态筛选", ["全部", "仅运行中", "仅已结束"], key="batch_status_filter")
        batch_gh_options = ["全部温室"] + sorted({b["gh_name"] for b in all_batches})
        gh_filter = filter_col2.selectbox("温室筛选", batch_gh_options, key="batch_gh_filter")
        keyword_filter = filter_col3.text_input("关键词检索", placeholder="按作物、品种或批次编号筛选", key="batch_keyword_filter")

        filtered_batches = []
        keyword_text = keyword_filter.strip().lower()
        for batch in all_batches:
            if status_filter == "仅运行中" and batch["status"] != 1:
                continue
            if status_filter == "仅已结束" and batch["status"] != 0:
                continue
            if gh_filter != "全部温室" and batch["gh_name"] != gh_filter:
                continue
            search_text = " ".join([
                str(batch.get("batch_id", "")),
                str(batch.get("gh_name", "")),
                str(batch.get("crop_name", "")),
                str(batch.get("variety", "")),
            ]).lower()
            if keyword_text and keyword_text not in search_text:
                continue
            filtered_batches.append(batch)

        if not filtered_batches:
            st.info("当前筛选条件下没有批次记录。")
        else:
            for batch in filtered_batches:
                batch_id = batch["batch_id"]
                start_dt = normalize_dt(batch.get("start_time"))
                harvest_dt = normalize_dt(batch.get("expected_harvest"))
                days_passed = max(0, (get_local_now() - start_dt).days) if start_dt else 0
                total_days = (harvest_dt - start_dt).days if start_dt and harvest_dt else 0
                progress = min(100, max(0, int(days_passed / total_days * 100))) if total_days > 0 else 0
                days_left = (harvest_dt.date() - today).days if harvest_dt else None
                latest_orders = [order for order in recent_work_orders if order.get("batch_id") == batch_id][:3]
                status_icon = "🟢 运行中" if batch["status"] == 1 else "⚪ 已结束"
                expander_title = f"{status_icon} | {format_batch_label(batch)}"

                with st.expander(expander_title, expanded=(batch["status"] == 1)):
                    top_c1, top_c2, top_c3, top_c4 = st.columns([1, 1, 1, 2])
                    top_c1.metric("已种植天数", f"{days_passed} 天")
                    top_c2.metric("工单归档数", f"{batch.get('work_order_count', 0)} 条")
                    if days_left is None:
                        top_c3.metric("采收倒计时", "未设置")
                    else:
                        top_c3.metric("采收倒计时", f"{days_left} 天")
                    with top_c4:
                        st.write("📅 **生长进度**")
                        st.progress(progress / 100 if progress else 0.0, text=f"已完成 {progress}%")

                    info_col, action_col = st.columns([1.2, 1.8], gap="large")
                    with info_col:
                        st.write(f"**开始日期**: {format_date(batch.get('start_time'))}")
                        st.write(f"**预计采收**: {format_date(batch.get('expected_harvest'))}")
                        st.write(f"**当前阶段**: `{batch.get('current_stage') or '未标注'}`")
                        last_orders_for_batch = [order for order in recent_work_orders if order.get("batch_id") == batch_id]
                        if last_orders_for_batch:
                            latest_order = last_orders_for_batch[0]
                            latest_start, latest_finish = get_work_order_time_window(latest_order)
                            st.write(
                                f"**最近工单**: {format_date(latest_start, with_time=True)}"
                                f" ~ {format_date(latest_finish, with_time=True)}"
                            )
                        else:
                            st.write("**最近工单**: 暂无")
                        if days_left is not None and days_left < 0 and batch["status"] == 1:
                            st.warning("该批次已超过预计采收日期，建议尽快处理或关闭批次。")

                    with action_col:
                        edit_c1, edit_c2 = st.columns(2)
                        next_stage = edit_c1.selectbox(
                            "更新阶段",
                            stage_options,
                            index=stage_index(batch.get("current_stage")),
                            key=f"stage_edit_{batch_id}"
                        )
                        next_harvest = edit_c2.date_input(
                            "调整预计采收",
                            value=as_date_input_value(batch.get("expected_harvest"), start_dt.date() if start_dt else today),
                            key=f"harvest_edit_{batch_id}"
                        )
                        btn_c1, btn_c2 = st.columns(2)
                        if btn_c1.button("💾 保存批次信息", key=f"save_batch_{batch_id}", use_container_width=True):
                            if start_dt and next_harvest < start_dt.date():
                                st.warning("预计采收日期不能早于定植/播种日期。")
                            else:
                                conn = db_manager.get_connection()
                                try:
                                    with conn.cursor() as cursor:
                                        cursor.execute("""
                                            UPDATE batches
                                            SET current_stage = %s, expected_harvest = %s
                                            WHERE batch_id = %s
                                        """, (next_stage, next_harvest, batch_id))
                                    conn.commit()
                                    st.success(f"批次 {batch_id} 已更新。")
                                    st.rerun()
                                finally:
                                    conn.close()

                        if batch["status"] == 1 and btn_c2.button("🏁 标记为已结束", key=f"finish_batch_{batch_id}", use_container_width=True):
                            conn = db_manager.get_connection()
                            try:
                                with conn.cursor() as cursor:
                                    cursor.execute("UPDATE batches SET status = 0 WHERE batch_id = %s", (batch_id,))
                                conn.commit()
                                st.success(f"批次 {batch_id} 已结束。")
                                st.rerun()
                            finally:
                                conn.close()

                        delete_orders_flag = st.checkbox(
                            "删除该批次时同步删除关联工单",
                            value=True,
                            key=f"delete_orders_with_batch_{batch_id}"
                        )
                        if st.button("🗑️ 删除该批次", key=f"delete_batch_{batch_id}", use_container_width=True):
                            try:
                                delete_batch_with_orders(batch_id, delete_orders=delete_orders_flag)
                                st.success(f"批次 {batch_id} 已删除。")
                                st.rerun()
                            except Exception as e:
                                st.error(f"删除批次失败: {e}")

                        if latest_orders:
                            latest_df = pd.DataFrame([
                                {
                                    "开始时间": format_date(get_work_order_time_window(order)[0], with_time=True),
                                    "完成时间": format_date(get_work_order_time_window(order)[1], with_time=True),
                                    "作业类型": order.get("task_type", ""),
                                    "负责人": order.get("operator", ""),
                                    "耗时(分钟)": format_duration_value(order.get("duration_mins")),
                                    "内容": order.get("content", "")
                                }
                                for order in latest_orders
                            ])
                            st.dataframe(latest_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("该批次暂未归档工单。")

        st.divider()
        st.subheader("📈 批次环境回溯")
        track_batches = active_batches if active_batches else all_batches
        if not track_batches:
            st.info("暂无批次，无法生成环境回溯曲线。")
        else:
            track_labels = [format_batch_label(batch) for batch in track_batches]
            track_col1, track_col2, track_col3 = st.columns([1.4, 1.2, 1])
            selected_track_label = track_col1.selectbox("选择批次", track_labels, key="batch_track_label")
            selected_batch = batch_lookup[selected_track_label]
            sensor_options = load_greenhouse_sensor_options(selected_batch["gh_name"])

            if not sensor_options:
                st.warning(f"【{selected_batch['gh_name']}】暂无可用的数值型环境传感器。")
            else:
                sensor_labels = [f"{sensor['sensor_name']} ({sensor['unit'] or '无单位'})" for sensor in sensor_options]
                default_sensor_index = 0
                for idx, sensor in enumerate(sensor_options):
                    if "温度" in sensor["sensor_name"] or "空温" in sensor["sensor_name"]:
                        default_sensor_index = idx
                        break
                selected_sensor_label = track_col2.selectbox("环境指标", sensor_labels, index=default_sensor_index, key="batch_track_sensor")
                bucket_label = track_col3.selectbox("聚合粒度", list(bucket_options.keys()), index=0, key="batch_track_bucket")
                selected_sensor = sensor_options[sensor_labels.index(selected_sensor_label)]
                history_df = load_batch_history(
                    selected_batch["gh_name"],
                    selected_sensor["sensor_name"],
                    selected_batch["start_time"],
                    bucket_options[bucket_label]
                )

                if history_df.empty:
                    st.warning(
                        f"在【{selected_batch['gh_name']}】中未找到自 {format_date(selected_batch['start_time'])} 起的"
                        f"【{selected_sensor['sensor_name']}】历史数据。"
                    )
                else:
                    metric_c1, metric_c2, metric_c3 = st.columns(3)
                    metric_c1.metric("均值", f"{history_df['value'].mean():.2f}{selected_sensor['unit'] or ''}")
                    metric_c2.metric("最高值", f"{history_df['value'].max():.2f}{selected_sensor['unit'] or ''}")
                    metric_c3.metric("最低值", f"{history_df['value'].min():.2f}{selected_sensor['unit'] or ''}")

                    fig_batch = px.line(
                        history_df,
                        x="bucket_time",
                        y="value",
                        title=f"批次 {selected_batch['batch_id']} - 【{selected_batch['crop_name']}】环境复盘",
                        labels={
                            "bucket_time": "时间",
                            "value": f"{selected_sensor['sensor_name']} ({selected_sensor['unit'] or '均值'})"
                        }
                    )
                    fig_batch.update_traces(line_shape="spline", line=dict(color="#00CC96", width=2))
                    apply_growth_stage_overlay(
                        fig_batch,
                        selected_batch["crop_name"],
                        normalize_dt(selected_batch["start_time"]),
                        get_local_now()
                    )
                    fig_batch.update_layout(height=420, margin={"t": 50, "b": 0}, hovermode="x unified")
                    st.plotly_chart(fig_batch, use_container_width=True)

    with create_tab:
        st.subheader("➕ 开启新的种植批次")
        if not device_names:
            st.warning("当前没有可用温室台账，请先同步设备数据后再创建批次。")
        else:
            with st.form("create_batch_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                b_gh = c1.selectbox("目标大棚", device_names, key="create_batch_gh")
                b_crop = c2.text_input("作物名称", placeholder="例如：结球生菜")
                b_variety = c1.text_input("品种名称", placeholder="例如：北极星一号")
                b_stage = c2.selectbox("初始生长阶段", stage_options[:-1], key="create_batch_stage")
                b_start = c1.date_input("定植/播种日期", value=get_local_now().date())
                b_harvest = c2.date_input("预计采收日期", value=(get_local_now() + timedelta(days=45)).date())
                submit_batch = st.form_submit_button("🚀 确认开启批次", type="primary", use_container_width=True)

                if submit_batch:
                    crop_name = b_crop.strip()
                    variety_name = b_variety.strip() or None
                    has_active_same_gh = any(batch["gh_name"] == b_gh and batch["status"] == 1 for batch in active_batches)

                    if not crop_name:
                        st.warning("请填写作物名称。")
                    elif b_harvest < b_start:
                        st.warning("预计采收日期不能早于定植/播种日期。")
                    elif has_active_same_gh:
                        st.warning(f"【{b_gh}】当前已有运行中的批次，请先结束原批次再开启新批次。")
                    else:
                        conn = db_manager.get_connection()
                        try:
                            with conn.cursor() as cursor:
                                cursor.execute("""
                                    INSERT INTO batches (gh_name, crop_name, variety, start_time, expected_harvest, current_stage, status)
                                    VALUES (%s, %s, %s, %s, %s, %s, 1)
                                """, (b_gh, crop_name, variety_name, b_start, b_harvest, b_stage))
                            conn.commit()
                            st.success(f"✅ 批次创建成功：{b_gh} 已进入【{crop_name}】种植周期。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"创建失败: {e}")
                        finally:
                            conn.close()

    with order_tab:
        left_col, right_col = st.columns([1.2, 1.8], gap="large")

        with left_col:
            st.subheader("📑 标准化电子工单")
            if not active_batch_labels:
                st.info("暂无运行中的批次，当前只能查看历史工单。")
            with st.form("sop_form", clear_on_submit=True):
                f1, f2, f3 = st.columns([2, 2, 1])
                if active_batch_labels:
                    selected_batch_label = f1.selectbox("关联批次", active_batch_labels, key="work_order_batch")
                else:
                    selected_batch_label = f1.selectbox("关联批次", ["无可用批次"], disabled=True, key="work_order_batch_disabled")
                task_type = f2.selectbox("作业类型 (SOP)", task_options[:-1], key="work_order_task_type")
                duration = f3.number_input("耗时(分钟)", min_value=1, value=30)
                operator = st.text_input("操作负责人", placeholder="输入执行人姓名")
                details = st.text_area("作业明细内容", placeholder="例如：设定 EC 值 1.5，开启侧窗通风 30%...")
                submitted = st.form_submit_button("💾 生成并归档工单", type="primary", use_container_width=True)

                if submitted:
                    if not active_batch_labels:
                        st.warning("当前没有可关联的运行中批次。")
                    elif not operator.strip():
                        st.warning("请填写操作负责人。")
                    elif not details.strip():
                        st.warning("请填写作业明细内容。")
                    else:
                        selected_batch = batch_lookup[selected_batch_label]
                        try:
                            save_work_order_records([(
                                selected_batch["batch_id"],
                                selected_batch["gh_name"],
                                task_type,
                                operator.strip(),
                                details.strip(),
                                duration
                            )])
                            st.success(f"✅ 【{task_type}】已归档到批次 {selected_batch['batch_id']}。")
                            st.rerun()
                        except Exception as e:
                            st.error(f"工单存入失败: {e}")

        with right_col:
            st.subheader("🗂️ 工单历史与追踪")
            order_filter_col1, order_filter_col2, order_filter_col3 = st.columns([1.4, 1.1, 1.3])
            order_batch_options = ["全部批次"] + [format_batch_label(batch) for batch in all_batches]
            order_gh_options = ["全部温室"] + sorted({order["gh_name"] for order in recent_work_orders if order.get("gh_name")})
            order_type_options = ["全部作业"] + sorted({order["task_type"] for order in recent_work_orders if order.get("task_type")})
            selected_order_batch = order_filter_col1.selectbox("批次筛选", order_batch_options, key="order_history_batch")
            selected_order_gh = order_filter_col2.selectbox("温室筛选", order_gh_options, key="order_history_gh")
            selected_order_type = order_filter_col3.selectbox("类型筛选", order_type_options, key="order_history_type")
            order_keyword = st.text_input("工单检索", placeholder="按负责人、内容关键词检索", key="order_history_keyword")

            filtered_orders = []
            order_keyword_text = order_keyword.strip().lower()
            for order in recent_work_orders:
                if selected_order_batch != "全部批次":
                    target_batch = batch_lookup[selected_order_batch]
                    if order.get("batch_id") != target_batch["batch_id"]:
                        continue
                if selected_order_gh != "全部温室" and order.get("gh_name") != selected_order_gh:
                    continue
                if selected_order_type != "全部作业" and order.get("task_type") != selected_order_type:
                    continue
                order_search_text = " ".join([
                    str(order.get("operator", "")),
                    str(order.get("content", "")),
                    str(order.get("task_type", "")),
                    str(order.get("gh_name", "")),
                ]).lower()
                if order_keyword_text and order_keyword_text not in order_search_text:
                    continue
                filtered_orders.append(order)

            total_duration = sum(int(order.get("duration_mins") or 0) for order in filtered_orders)
            stat_c1, stat_c2 = st.columns(2)
            stat_c1.metric("命中工单数", f"{len(filtered_orders)} 条")
            stat_c2.metric("累计工时", f"{total_duration} 分钟")

            clean_c1, clean_c2 = st.columns(2)
            if clean_c1.button("🧹 清空全部工单", use_container_width=True, key="delete_all_orders"):
                try:
                    bulk_delete_test_data(delete_all_orders=True)
                    st.success("全部工单已清空。")
                    st.rerun()
                except Exception as e:
                    st.error(f"清空工单失败: {e}")
            if clean_c2.button("🧹 删除全部已结束批次", use_container_width=True, key="delete_finished_batches"):
                try:
                    bulk_delete_test_data(delete_finished_batches=True)
                    st.success("全部已结束批次及其关联工单已删除。")
                    st.rerun()
                except Exception as e:
                    st.error(f"清理已结束批次失败: {e}")

            if not filtered_orders:
                st.info("当前筛选条件下没有工单记录。")
            else:
                orders_df = pd.DataFrame([
                    {
                        "开始时间": format_date(get_work_order_time_window(order)[0], with_time=True),
                        "完成时间": format_date(get_work_order_time_window(order)[1], with_time=True),
                        "批次ID": order.get("batch_id"),
                        "温室": order.get("gh_name"),
                        "作物": order.get("crop_name") or "",
                        "当前阶段": order.get("current_stage") or "",
                        "作业类型": order.get("task_type"),
                        "负责人": order.get("operator"),
                        "耗时(分钟)": format_duration_value(order.get("duration_mins")),
                        "内容": order.get("content")
                    }
                    for order in filtered_orders
                ])
                st.dataframe(orders_df, use_container_width=True, hide_index=True)
                order_delete_options = {
                    f"工单ID:{order['id']} | {format_date(get_work_order_time_window(order)[0], with_time=True)} | "
                    f"{order.get('gh_name', '未知温室')} | {order.get('task_type', '未知类型')}": order["id"]
                    for order in filtered_orders
                }
                delete_order_col1, delete_order_col2 = st.columns([3, 1])
                selected_delete_order_label = delete_order_col1.selectbox(
                    "选择要删除的工单",
                    list(order_delete_options.keys()),
                    key="delete_work_order_select"
                )
                if delete_order_col2.button("🗑️ 删除工单", use_container_width=True, key="delete_work_order_btn"):
                    try:
                        delete_work_order(order_delete_options[selected_delete_order_label])
                        st.success("工单已删除。")
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除工单失败: {e}")
                csv_data = orders_df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "📥 下载工单台账 CSV",
                    data=csv_data,
                    file_name="工单台账.csv",
                    mime="text/csv"
                )

    with control_tab:
        st.subheader("🚀 多设备一键联控")
        st.caption("按温室统一下发动作，并可自动归档成联控工单。")
        if DEBUG_MODE:
            st.warning("当前处于测试模式：联控仅展示将要下发的指令，不会真实触达硬件。")
        if not online_devices:
            st.error("当前无在线设备可控。")
        else:
            ctrl_left, ctrl_right = st.columns([1.2, 1.8], gap="large")
            with ctrl_left:
                default_targets = online_devices.copy()
                target_ghs = st.multiselect("1. 选择需要联控的在线温室", online_devices, default=default_targets)

                switch_names = set()
                for device in st.session_state.device_data:
                    if device.get("deviceName") not in target_ghs:
                        continue
                    for sensor in device.get("sensorsList") or []:
                        if sensor.get("sensorTypeId") in [2, 5, 6]:
                            sensor_name = (sensor.get("sensorName") or "").strip()
                            if sensor_name:
                                switch_names.add(sensor_name)

                action_options = []
                for sensor_name in sorted(switch_names):
                    action_options.append(f"🟢 打开所有 {sensor_name}")
                    action_options.append(f"🔴 关闭所有 {sensor_name}")
                if not action_options:
                    action_options = ["⚠️ 选中的温室暂无可控设备"]

                action = st.selectbox("2. 选择统一执行动作", action_options, key="control_action_select")
                matched_target_count = 0
                if action_options and "⚠️" not in action:
                    target_sensor_name = action.replace("🟢 打开所有 ", "").replace("🔴 关闭所有 ", "")
                    for device in st.session_state.device_data:
                        if device.get("deviceName") not in target_ghs:
                            continue
                        for sensor in device.get("sensorsList") or []:
                            if sensor.get("sensorTypeId") in [2, 5, 6] and (sensor.get("sensorName") or "").strip() == target_sensor_name:
                                matched_target_count += 1
                st.caption(f"预计触达 {matched_target_count} 个可控对象。")

                archive_control = st.checkbox("将本次联控自动归档为工单", value=bool(active_batches))
                control_operator = st.text_input("执行负责人", value="系统联控" if archive_control else "", key="control_operator")
                control_note = st.text_area("执行说明", placeholder="例如：中午棚内升温较快，统一打开顶部通风。", key="control_note")

                if st.button("🚀 下发联控指令", type="primary", use_container_width=True):
                    if not target_ghs:
                        st.warning("请至少选择一个温室。")
                    elif "⚠️" in action:
                        st.error("当前无有效指令可下发。")
                    else:
                        api_client, client_error = ensure_api_client()
                        if client_error:
                            st.error(client_error)
                        elif api_client:
                            is_open = "打开" in action
                            target_switcher_val = 1 if is_open else 0
                            target_sensor_name = action.replace("🟢 打开所有 ", "").replace("🔴 关闭所有 ", "")
                            success_cnt, fail_cnt, skip_cnt, details_log = execute_batch_control(
                                client=api_client,
                                target_ghs=target_ghs,
                                target_sensor_name=target_sensor_name,
                                target_switcher_val=target_switcher_val,
                            )
                            archive_count = 0
                            skipped_archive_ghs = []
                            if archive_control and details_log:
                                archive_count, skipped_archive_ghs = archive_control_orders(
                                    target_ghs=target_ghs,
                                    action_label=action,
                                    operator_name=control_operator.strip(),
                                    note_text=control_note.strip(),
                                    details_log=details_log,
                                    running_batches=active_batches
                                )

                            st.session_state["control_execution_result"] = {
                                "summary": {
                                    "success": success_cnt,
                                    "fail": fail_cnt,
                                    "skip": skip_cnt,
                                    "archive_count": archive_count,
                                    "skipped_archive_ghs": skipped_archive_ghs,
                                    "action": action,
                                    "target_ghs": target_ghs,
                                },
                                "details": details_log
                            }
                            st.rerun()
            with ctrl_right:
                result = st.session_state.get("control_execution_result")
                if not result:
                    st.info("执行后的联控明细、归档结果会显示在这里。")
                else:
                    summary = result["summary"]
                    summary_text = f"成功 {summary['success']} 条，跳过 {summary['skip']} 条，失败 {summary['fail']} 条。"
                    if summary["archive_count"] > 0:
                        summary_text += f" 已归档 {summary['archive_count']} 条联控工单。"
                    if summary["skipped_archive_ghs"]:
                        skipped_text = "、".join(summary["skipped_archive_ghs"])
                        summary_text += f" 以下温室无运行中批次，未自动归档：{skipped_text}。"

                    if summary["fail"] == 0 and summary["success"] > 0:
                        st.success(summary_text)
                    elif summary["fail"] > 0:
                        st.warning(summary_text)
                    elif summary["success"] == 0 and summary["skip"] > 0:
                        st.info("所选大棚设备已全部处于目标状态，无需重复下发。")
                    else:
                        st.error("未匹配到可控的物理设备实体。")

                    st.write(f"**最近联控动作**: {summary['action']}")
                    st.write(f"**目标温室**: {'、'.join(summary['target_ghs'])}")

                    details = result.get("details") or []
                    if details:
                        st.dataframe(pd.DataFrame(details), use_container_width=True, hide_index=True)

# ----------------- 页面五：策略与预警 -----------------
elif menu == "⚙️ 策略与预警":
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
            if common_metrics is None:
                common_metrics = current_gh_metrics # 第一个大棚作为初始集合
            else:
                common_metrics = common_metrics.intersection(current_gh_metrics) # 连续求交集
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

                    if target_gh == "全局所有大棚":
                        st.success(f"✅ 已成功为 **{len(actual_targets)}** 个大棚批量部署【{target_metric}】的报警策略！")
                    else:
                        st.success(f"✅ 【{target_gh}】的【{target_metric}】报警策略部署成功！")

                except Exception as e:
                    st.error(f"⚠️ 保存失败: {e}")
