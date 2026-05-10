



with tab2:
        # ---------------- 【需求3】前中后区域聚合分析 ----------------
        st.subheader("大棚微气候区域温差分析 (前/中/后)")
        st.markdown("通过分析历史时间序列数据，对比大棚两端与中间的微气候差异（如通风死角、光照不均引起的温差）。")
        
        # 1. UI 选择器
        c_gh2, c_base = st.columns(2)
        device_names = sorted(list(set([d.get("deviceName", "未知") for d in st.session_state.device_data])))
        selected_gh_tab2 = c_gh2.selectbox("🏠 选择要分析的大棚", device_names, key="gh_tab2")
        
        # 假设 base_metric_opts 是你在外部定义的基础指标（如 ["温度", "湿度", "CO2", "土壤pH"]）
        agg_base = c_base.selectbox("📊 选择要对比的基础指标", base_metric_opts)
        
        # 2. 动态寻找前、中、后对应的传感器名称
        target_device = next((d for d in st.session_state.device_data if d.get("deviceName") == selected_gh_tab2), None)
        zone_sensors = {}  # 用于存储匹配到的传感器: {"前区": "1号CO2", "中区": "2号CO2", ...}
        
        if target_device and "sensorsList" in target_device:
            for s in target_device["sensorsList"]:
                name = s.get("sensorName", "")
                
                # 过滤控制设备和开关
                if str(s.get("sensor_type_id")) == "2" or "switcher" in s:
                    continue
                    
                # 如果这个传感器名字包含了我们选的基础指标 (比如 "温度")
                if agg_base in name:
                    # 模式匹配找区域
                    if any(k in name for k in ["1号", "1组", "前"]):
                        zone_sensors["前区(1号/1组)"] = name
                    elif any(k in name for k in ["2号", "2组", "中"]):
                        zone_sensors["中区(2号/2组)"] = name
                    elif any(k in name for k in ["3号", "3组", "后"]):
                        zone_sensors["后区(3号/3组)"] = name
                        
        if len(zone_sensors) < 2:
            st.warning(f"⚠️ 在【{selected_gh_tab2}】中，未能找到至少两个带有前/中/后标识的【{agg_base}】传感器，无法进行区域对比。")
            st.info(f"系统当前识别到的相关传感器有: {[s.get('sensorName') for s in target_device.get('sensorsList', []) if agg_base in s.get('sensorName', '')]}")
        else:
            # 提取匹配到的真实传感器名称列表
            actual_sensor_names = list(zone_sensors.values())
            
            with st.spinner(f"正在拉取【{selected_gh_tab2}】历史 {agg_base} 分布数据..."):
                db_manager.init_db() 
                conn = db_manager.get_connection()
                history_records = []
                
                try:
                    with conn.cursor() as cursor:
                        # 动态生成 SQL 的 IN 占位符 (防止 SQL 注入)
                        placeholders = ', '.join(['%s'] * len(actual_sensor_names))
                        sql = f"""
                            SELECT 
                                sh.add_time AS record_time, 
                                s.sensor_name, 
                                sh.value AS sensor_value 
                            FROM sensor_history sh
                            JOIN sensors s ON sh.sensor_id = s.sensor_id
                            JOIN devices d ON s.device_id = d.device_id
                            WHERE d.gh_name = %s 
                              AND sh.add_time >= %s
                              AND s.sensor_name IN ({placeholders})
                        """
                        # 执行查询：参数拼装
                        query_params = [selected_gh_tab2, start_time] + actual_sensor_names
                        cursor.execute(sql, query_params)
                        history_records = cursor.fetchall()
                except Exception as e:
                    st.error(f"数据库查询失败: {e}")
                finally:
                    conn.close()
                
                if not history_records:
                    st.info(f"暂无【{selected_gh_tab2}】在此时段内的历史关联数据。")
                else:
                    df_raw = pd.DataFrame(history_records)
                    df_raw['sensor_value'] = pd.to_numeric(df_raw['sensor_value'], errors='coerce')
                    df_raw['record_time'] = pd.to_datetime(df_raw['record_time']) 
                    
                    # 🌟 真实数据区间校验
                    actual_start = df_raw['record_time'].min()
                    actual_end = df_raw['record_time'].max()
                    if (actual_start - start_time).total_seconds() > 7200:
                        str_start = actual_start.strftime('%Y-%m-%d %H:%M')
                        str_end = actual_end.strftime('%Y-%m-%d %H:%M')
                        st.info(
                            f"💡 **数据区间动态调整**：您选择了分析【{analysis_range}】，"
                            f"但该大棚可追溯的最早记录始于 {str_start}。\n\n"
                            f"实际区域分析的数据区间为：**{str_start} 至 {str_end}**。"
                        )
                    df_raw['record_time'] = df_raw['record_time'].dt.round('10min')
                    
                    # 为了在图例中显示好看的 "前区", "中区", 我们把 sensor_name 映射过去
                    # 反转字典 key-value 关系: {"1号CO2": "前区(1号/1组)", ...}
                    name_to_zone = {v: k for k, v in zone_sensors.items()}
                    df_raw['区域'] = df_raw['sensor_name'].map(name_to_zone)
                    
                    # 过滤掉映射失败的脏数据，并按时间+区域求平均
                    df_clean = df_raw.dropna(subset=['区域', 'sensor_value'])
                    df_grouped = df_clean.groupby(['record_time', '区域'])['sensor_value'].mean().reset_index()
                    
                    if df_grouped.empty:
                        st.warning("处理后无有效数据可供绘图。")
                    else:
                        st.markdown("#### 📈 时序波动趋势对比")
                        # 1. 绘制时序折线图 (看每一刻的变化)
                        fig_line = px.line(
                            df_grouped, 
                            x='record_time', 
                            y='sensor_value', 
                            color='区域',
                            title=f"【{selected_gh_tab2}】{agg_base} 前中后区域历史走势",
                            markers=True
                        )
                        # 优化折线图显示效果
                        fig_line.update_traces(marker=dict(size=4), line=dict(width=2))
                        fig_line.update_layout(xaxis_title="采集时间", yaxis_title=f"{agg_base} 数值", hovermode="x unified")
                        st.plotly_chart(fig_line, use_container_width=True)
                        
                        st.markdown("#### 📊 周期整体均值聚合对比")
                        # 2. 计算整个周期的均值，绘制你原本想要的柱状图
                        df_mean = df_grouped.groupby('区域')['sensor_value'].mean().reset_index()
                        
                        fig_bar = px.bar(
                            df_mean, 
                            x='区域', 
                            y='sensor_value', 
                            color='区域', 
                            text_auto='.2f', # 柱子上显示保留2位小数的数值
                            title=f"【{selected_gh_tab2}】本周期内 {agg_base} 各区域平均值",
                            color_discrete_sequence=px.colors.qualitative.Pastel
                        )
                        fig_bar.update_layout(xaxis_title="大棚区域", yaxis_title=f"平均 {agg_base}", showlegend=False)
                        st.plotly_chart(fig_bar, use_container_width=True)