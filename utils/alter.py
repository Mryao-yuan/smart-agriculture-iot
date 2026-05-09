import requests
import streamlit as st



def user_webhook_check(webhook_url):
    if not webhook_url.startswith("https://oapi.dingtalk.com/robot/send?access_token="):
        st.error("❌ Webhook 地址必须以 https://oapi.dingtalk.com/robot/send?access_token= 开头")
        return False
    token_part = webhook_url.split("access_token=")[-1]
    if len(token_part) != 64:
        st.error("❌ Webhook 地址中的 access_token 长度不正确，应为64位")
        return False
    st.success("✅ Webhook 地址格式正确")
    return True

# 钉钉网址确认
def dingding_webhook_check(webhook_url):
    payload = {
    "msgtype": "text",
    "text": {
        "content": "预警：测试消息"
    }}

    response = requests.post(webhook_url, json=payload)
    return response.json()['errmsg'] != "ok"

