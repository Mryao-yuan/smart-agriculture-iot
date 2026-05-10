import re
import pandas as pd
import streamlit as st
from datetime import datetime



def extract_gh_num(name):
    # 使用正则表达式提取字符串开头的数字，例如从 "01号青海..." 提取出 1
    match = re.search(r'^(\d+)', str(name))
    return int(match.group(1)) if match else 9999



def get_sorted_devices(device_list):
    """
    将设备列表按照名称开头的数字进行排序
    """
    def extract_num(name):
        match = re.search(r'^(\d+)', str(name))
        return int(match.group(1)) if match else 9999
    
    return sorted(device_list, key=lambda x: extract_num(x.get('deviceName', '')))

def parse_zone(sensor_name):

    if any(k in sensor_name for k in ["1号", "1组", "前"]):
        return "前区(1号/1组)"

    elif any(k in sensor_name for k in ["2号", "2组", "中"]):
        return "中区(2号/2组)"

    elif any(k in sensor_name for k in ["3号", "3组", "后"]):
        return "后区(3号/3组)"

    return None

def process_history_records(history_records, start_time, analysis_range, record_col="record_time", value_col="sensor_value"):
    """
    处理历史数据记录：
    - 转为 DataFrame
    - 数值字段转换为 float
    - 时间字段转换为 datetime 并对齐（降采样）
    - 动态调整实际起止时间，如果最早数据晚于 start_time
    """

    if not history_records:
        st.info(f"暂无在此时段内的历史数据。")
        return pd.DataFrame(), None, None

    df_raw = pd.DataFrame(history_records)
    df_raw[value_col] = pd.to_numeric(df_raw[value_col], errors='coerce')

    # 确保时间格式
    df_raw[record_col] = pd.to_datetime(df_raw[record_col])
    df_raw[record_col] = df_raw[record_col].dt.round('10min')  # 时间对齐，降采样

    actual_start = df_raw[record_col].min()
    actual_end = df_raw[record_col].max()

    # 动态调整区间
    if (actual_start - start_time).total_seconds() > 7200:  # 2h阈值
        str_start = actual_start.strftime('%Y-%m-%d %H:%M')
        str_end = actual_end.strftime('%Y-%m-%d %H:%M')
        st.info(
            f"💡 **数据区间动态调整**：您选择了分析【{analysis_range}】，"
            f"但可追溯的最早记录始于 {str_start}。\n\n"
            f"实际分析区间为：**{str_start} 至 {str_end}**。"
        )
    else:
        str_start = start_time.strftime('%Y-%m-%d %H:%M')
        str_end = actual_end.strftime('%Y-%m-%d %H:%M')

    return df_raw, actual_start, actual_end