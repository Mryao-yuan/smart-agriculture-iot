import streamlit as st
import json
import os
import random
import base64
import string
import time
from captcha.image import ImageCaptcha  

def get_base64_of_bin_file(bin_file):
    """读取图片文件并转换为 base64 字符串"""
    try:
        with open(bin_file, 'rb') as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        return ""
    
DEFAULT_PASS = "123456"

def load_users(json_path):
    if not os.path.exists(json_path):
        default_users = {"admin": DEFAULT_PASS, "user": DEFAULT_PASS}
        with open(json_path, "w") as f:
            json.dump(default_users, f)
        return default_users
    with open(json_path, "r") as f:
        return json.load(f)

def save_users(users, json_path):
    with open(json_path, "w") as f:
        json.dump(users, f)

def generate_captcha():
    """生成4位随机验证码字符和图片"""
    image = ImageCaptcha(width=200, height=60)
    captcha_text = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    data = image.generate(captcha_text)
    return captcha_text, data

def check_password(bg_path, json_path="./users.json"):
    """返回 `True` 如果登录成功"""
    users_db = load_users(json_path)

    if "captcha_correct_text" not in st.session_state:
        code, img_data = generate_captcha()
        st.session_state["captcha_correct_text"] = code
        st.session_state["captcha_image"] = img_data

    def refresh_captcha():
        """刷新验证码的回调"""
        code, img_data = generate_captcha()
        st.session_state["captcha_correct_text"] = code
        st.session_state["captcha_image"] = img_data

    def password_entered():
        """检查用户名、密码和验证码"""
        # 🌟 优化：加入 .strip() 清除无意间输入的空格
        input_user = st.session_state.get("username", "").strip()
        input_pass = st.session_state.get("password", "")
        input_captcha = st.session_state.get("captcha_input", "").upper().strip()

        # 1. 检查验证码
        if input_captcha != st.session_state["captcha_correct_text"]:
            st.session_state["login_error"] = "❌ 验证码错误，请重试"
            refresh_captcha() 
            return
            
        # 2. 检查用户名和密码
        if input_user in users_db and users_db[input_user] == input_pass:
            st.session_state["password_correct"] = True
            st.session_state["current_user"] = input_user
            
            # 登录成功，清理缓存字段
            if "password" in st.session_state:
                del st.session_state["password"]
            if "captcha_input" in st.session_state:
                del st.session_state["captcha_input"]
            if "login_error" in st.session_state:
                del st.session_state["login_error"]
        else:
            st.session_state["password_correct"] = False
            st.session_state["login_error"] = "😕 用户名或密码错误"
            refresh_captcha()

    def change_password_func():
        u = st.session_state.get("chg_user", "").strip()
        old_p = st.session_state.get("chg_old_pass", "")
        new_p = st.session_state.get("chg_new_pass", "")
        confirm_p = st.session_state.get("chg_confirm_pass", "")

        if u not in users_db:
            st.warning("用户不存在")
            return
        if users_db[u] != old_p:
            st.error("旧密码错误")
            return
        if new_p != confirm_p:
            st.error("两次新密码输入不一致")
            return
        if len(new_p) < 6:
            st.warning("新密码长度不能少于6位")
            return

        # 更新并保存
        users_db[u] = new_p
        save_users(users_db, json_path)
        st.success("✅ 密码修改成功！请返回登录。")
        time.sleep(1)
        
    def inject_css(bg_path):
        bin_str = get_base64_of_bin_file(bg_path)
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url("data:image/png;base64,{bin_str}");
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
            
            div[data-testid="stAppViewContainer"] > section[data-testid="stMain"] > div.block-container {{
                padding-top: 2rem;
                padding-bottom: 2rem;
                display: flex;
                flex-direction: column;
                justify-content: center; 
                min-height: 100vh;       
            }}
            
            div[data-testid="column"]:nth-of-type(2) > div {{
                background-color: rgba(255, 255, 255, 0.95);
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
        
    def show_login_form(bg_path):
        inject_css(bg_path)  
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("""
                <div style='text-align: center; margin-bottom: 20px;'>
                    <div style='font-size: 42px; font-weight: bold; color: #333;'>智慧温室</div>
                    <div style='font-size: 35px; font-weight: bold; color: #333;'>IoT 平台</div>
                </div>
                """, unsafe_allow_html=True)
            
            tab_login, tab_change = st.tabs(["🔑 登录", "🛠️ 修改密码"])

            with tab_login:
                st.text_input("用户名", key="username")
                st.text_input("密码", type="password", key="password")
                
                # --- 验证码区域 ---
                c_img, c_input = st.columns([1, 1])
                with c_img:
                    st.image(st.session_state["captcha_image"], width='stretch')
                    if st.button("🔄 换一张", key="btn_refresh_captcha"):
                        refresh_captcha()
                        st.rerun()
                with c_input:
                    st.text_input("验证码", key="captcha_input", placeholder="输入左侧字符")
                # ------------------

                st.button("登录", on_click=password_entered, width='stretch', type="primary")

                if "login_error" in st.session_state:
                    st.error(st.session_state["login_error"])

            with tab_change:
                st.text_input("用户名", key="chg_user")
                st.text_input("旧密码", type="password", key="chg_old_pass")
                st.text_input("新密码", type="password", key="chg_new_pass")
                st.text_input("确认新密码", type="password", key="chg_confirm_pass")
                st.button("确认修改", on_click=change_password_func, width='stretch')

    # === main pipeline ===
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
        
    # unlogin state show login form
    if not st.session_state["password_correct"]:
        show_login_form(bg_path)
        return False
    else:
        # 🌟 直接放行，再也没有强制改密码了！
        return True