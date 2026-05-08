import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# 导入你之前写好的 IotClient (假设保存在 iot_client.py 中)
# from iot_client import IotClient  
# 这里为了演示，我定义一个包含你原有方法的 Mock 类，实际使用时请取消上方注释，并删除这个 Mock 块

# ==================== 配置与初始化 ====================
st.set_page_config(page_title="智慧温室 IoT 中控台", layout="wide", page_icon="🌱")

# 初始化 Session State
if 'client' not in st.session_state:
    st.session_state.client = None # 实际使用：IotClient()
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'gh_status' not in st.session_state:
    # 模拟 9 个温室的初始状态 (1: 正常, 0: 离线, -1: 报警)
    st.session_state.gh_status = {f"棚 {i}": 1 for i in range(1, 10)}
    st.session_state.gh_status["棚 7"] = 0
    st.session_state.gh_status["棚 8"] = -1

# ==================== 左侧导航与登录 ====================
with st.sidebar:
    st.title("🌱 智慧农业平台")
    if not st.session_state.logged_in:
        st.subheader("系统登录")
        username = st.text_input("用户名", value="admin")
        password = st.text_input("密码", type="password", value="123456")
        if st.button("登录", use_container_width=True):
            # 实际接入：
            # res = st.session_state.client.login(username, password, "YOUR_API_KEY")
            # if res.get("flag") == "00":
            #     st.session_state.client.get_access_token(username, password)
            st.session_state.logged_in = True
            st.success("登录成功！")
            st.rerun()
    else:
        st.success(f"欢迎您, 管理员")
        menu = st.radio("导航菜单", ["🌐 全局沙盘 (9棚)", "🏠 单棚详控", "📈 跨棚数据分析", "⚙️ 联控与工单"])
        if st.button("退出登录"):
            st.session_state.logged_in = False
            st.rerun()

# ==================== 主体逻辑 ====================
if not st.session_state.logged_in:
    st.info("👈 请在左侧输入平台账号密码登录。")
    st.stop()

# ----------------- 需求 1: 动态显示 9 座温室位置与状态 -----------------
if menu == "🌐 全局沙盘 (9棚)":
    st.header("🌐 全局温室监控矩阵")
    st.markdown("红/黄/绿三色标识状态（报警/离线/正常）")
    
    cols = st.columns(3)
    for i in range(1, 10):
        gh_name = f"棚 {i}"
        status = st.session_state.gh_status[gh_name]
        
        with cols[(i-1) % 3]:
            # 用不同颜色卡片表示状态
            if status == 1:
                bg_color = "#e6f4ea" # 绿
                icon = "✅ 正常"
            elif status == 0:
                bg_color = "#fef7e0" # 黄
                icon = "⚠️ 离线"
            else:
                bg_color = "#fce8e6" # 红
                icon = "🚨 报警"
                
            st.markdown(f"""
            <div style="background-color:{bg_color}; padding:20px; border-radius:10px; margin-bottom:20px; text-align:center; border: 1px solid #ddd;">
                <h3 style="margin:0;">🌿 {gh_name}</h3>
                <p style="margin:5px 0 0 0; font-weight:bold;">{icon}</p>
                <p style="font-size:12px; color:#666;">温度: 24°C | 湿度: 65%</p>
            </div>
            """, unsafe_allow_html=True)

# ----------------- 需求 2, 5, 7: 单棚进入设备沙盘、实物建模、单设备操控、视频接入 -----------------
elif menu == "🏠 单棚详控":
    st.header("🏠 单棚设备详控与流媒体")
    selected_gh = st.selectbox("请选择要操作的温室", [f"棚 {i}" for i in range(1, 10)])
    
    col_video, col_ctrl = st.columns([2, 1])
    
    with col_video:
        st.subheader("📹 实时监控画面 (需求7)")
        # 这里可以是 iframe 接入 flv.js 或者 WebRTC 视频流
        st.video("https://www.w3schools.com/html/mov_bbb.mp4", format="video/mp4") 
        st.caption("注：实际项目中此处替换为监控摄像头取流地址")
        
        # 需求2：数字孪生/沙盘展示 (Streamlit 无法原生渲染高质量 3D，建议用图片占位或集成 iframe)
        st.info("💡 3D 沙盘：在 Streamlit 中，可使用 `streamlit.components.v1.iframe` 嵌入外部渲染好的 Three.js 页面。")

    with col_ctrl:
        st.subheader("🎛️ 实时数据与控制 (需求5)")
        # 实际调用：res = st.session_state.client.get_single_device_datas(...)
        st.metric(label="当前空气温度", value="26.5 °C", delta="1.2 °C")
        st.metric(label="当前土壤EC值", value="1.8 mS/cm", delta="-0.1 mS/cm")
        
        st.divider()
        st.markdown("**快速控制面板**")
        # 需求 11：远程控制与农事绑定 (弹窗机制)
        light = st.toggle("💡 补光灯")
        if light:
            # st.session_state.client.switcher_controller(device_no="D01", sensor_id=1, switcher=1)
            st.toast(f"指令已下发：{selected_gh} 补光灯开启")
            
        water = st.toggle("🌧️ 雾化系统")
        if water:
            st.toast(f"指令已下发：{selected_gh} 雾化开启")
            # 模拟联动农事表单弹窗 (Streamlit 没有传统弹窗，用展开组件替代)
            with st.expander("📝 自动生成工单：降温加湿记录", expanded=True):
                st.text_input("操作人", value="admin")
                st.text_area("操作备注", value="开启雾化，预计运行30分钟。")
                st.button("提交工单")

        roll = st.toggle("📜 卷膜机")

# ----------------- 需求 3, 4: 多维看板、跨棚对比、相关性分析 -----------------
elif menu == "📈 跨棚数据分析":
    st.header("📈 多维数据看板与跨棚对比")
    
    tab1, tab2 = st.tabs(["跨棚均值对比 (需求4)", "参数相关性分析 (需求3)"])
    
    with tab1:
        st.subheader("9棚实时均值对比")
        # 模拟调用 get_sensor_history 获取多设备数据
        compare_metric = st.selectbox("选择对比指标", ["空气温度 (°C)", "土壤湿度 (%)", "光照度 (Lux)"])
        
        # 使用 Plotly 绘制柱状图或曲线
        mock_data = pd.DataFrame({
            "温室": [f"棚 {i}" for i in range(1, 10)],
            "数值": [22, 24, 23.5, 26, 21, 28, 25, 22.5, 24.2]
        })
        fig = px.bar(mock_data, x="温室", y="数值", color="数值", color_continuous_scale="Viridis")
        st.plotly_chart(fig, use_container_width=True)
        
    with tab2:
        st.subheader("参数相关性分析：光照 vs 温度")
        # 散点图分析相关性
        df_corr = pd.DataFrame({
            "光照度(Lux)": [1000, 2000, 3000, 4500, 5000, 6000],
            "温度(°C)": [18, 20, 23, 26, 28, 30]
        })
        fig2 = px.scatter(df_corr, x="光照度(Lux)", y="温度(°C)", trendline="ols")
        st.plotly_chart(fig2, use_container_width=True)

# ----------------- 需求 6, 8, 9, 10: 批次联控、预警与工单 -----------------
elif menu == "⚙️ 联控与工单":
    st.header("⚙️ 批量联控与农事流转")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔄 多设备联控 (需求6)")
        target_ghs = st.multiselect("请勾选目标温室", [f"棚 {i}" for i in range(1, 10)], default=["棚 1", "棚 2", "棚 3"])
        target_device = st.selectbox("选择操作设备", ["统一开卷被机", "统一关卷被机", "统一开补光灯"])
        if st.button("🚀 执行批量指令", type="primary"):
            # 实际代码这里会使用 for 循环调用 IotClient
            # for gh in target_ghs:
            #    client.switcher_controller(...)
            st.success(f"成功向 {len(target_ghs)} 座温室下发了 【{target_device}】 指令！")
            
    with col2:
        st.subheader("📋 标准化工单与批次 (需求9, 10)")
        action = st.selectbox("电子工单模板", ["播种记录", "灌溉方案", "施肥与炼苗"])
        batch_no = st.text_input("关联批次号", value="SC-2026-05-07")
        st.date_input("操作日期")
        st.button("保存操作记录")
    
       
    st.divider()
    st.subheader("🚨 自动化预警中心 (钉钉推送)")
    st.markdown("当传感器数值超过设定范围时，系统将通过钉钉机器人实时向群内发送报警信息。")

    # --- 第一步：引导用户加入报警群 ---
    with st.expander("📢 第一步：加入大棚预警钉钉群", expanded=True):
        col_qr1, col_qr2 = st.columns([1, 2])
        # 这里放置你从钉钉群里保存的机器人二维码图片
        # 如果没有图片，可以用文字引导
        col_qr1.image("qrcode.png", caption="扫码加入运维群", width=150) 
        col_qr2.info("""
        **操作指引：**
        1. 手机钉钉扫码进入运维群。
        2. 群助手已配置机器人,异常数据报警。
        """)

    # --- 第二步：配置报警规则 ---
    st.markdown("---")
    st.markdown("### 第二步：设定阈值与推送地址")

    with st.form("alert_form"):
        c1, c2 = st.columns(2)
        target_gh = c1.selectbox("应用大棚", sorted_names)
        
        # 动态获取该大棚的指标选项（使用之前定义的 metric_opts）
        target_metric = c2.selectbox("监控指标基类", base_metric_opts) 
        
        col_v1, col_v2 = st.columns(2)
        max_val = col_v1.number_input("上限报警阈值", value=35.0, step=0.5)
        min_val = col_v2.number_input("下限报警阈值", value=10.0, step=0.5)
        
        # 钉钉 Webhook 地址输入
        webhook_url = st.text_input(
            "钉钉 Webhook 地址", 
            placeholder="https://oapi.dingtalk.com/robot/send?access_token=...",
            help="在钉钉群助手-添加机器人-自定义-获取此地址"
        )
        
        submit = st.form_submit_button("🚀 部署预警策略", type="primary")
        
        if submit:
            if not webhook_url.startswith("https://oapi.dingtalk.com/"):
                st.error("❌ 请输入有效的钉钉 Webhook 地址！")
            else:
                # --- 写入 TiDB 数据库 ---
                try:
                    import database_manager
                    # 建议数据库增加字段：target_gh, metric_name, max_val, min_val, ding_webhook
                    success = database_manager.save_alert_rule(
                        target_gh, target_metric, max_val, min_val, webhook_url
                    )
                    if success:
                        st.balloons()
                        st.success(f"✅ 策略已生效！系统将每10分钟监控【{target_gh}】的【{target_metric}】。")
                except Exception as e:
                    st.error(f"保存失败：{e}")