import streamlit as st

def load_local_css(file_name):
    """
    读取本地 CSS 文件并注入到 Streamlit 页面中
    """
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            css_content = f.read()
            st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"⚠️ 找不到样式文件: {file_name}")
        
def generate_sensor_card_html(s_name, val_color_style, s_val, s_unit, s_time, s_id):
    """
    生成传感器卡片的 HTML 字符串
    """
    return f"""
<div class="sensor-card">
<div class="sensor-label">{s_name}</div>
<div class="sensor-value" style="{val_color_style}">{s_val}<span class="sensor-unit">{s_unit}</span></div>
<div class="sensor-meta-box">
<div class="meta-row">
<span class="meta-icon">📅</span>
<span>{s_time}</span>
</div>
<div class="meta-row">
<span class="meta-icon">ID:</span>
<span>{s_id}</span>
</div>
</div>
</div>"""

# <span class="copy-text" title="单击选中即可复制" onclick="navigator.clipboard.writeText('{s_id}')">{s_id}</span>
