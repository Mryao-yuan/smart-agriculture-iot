import requests
import base64
import json

# 关闭警告
# requests.packages.urllib3.disable_warnings()

class IotClient:
    def __init__(self):
        self.host = "http://api.hjznjs.com"
        self.base_path = "/hapi"

        self.client_id = None
        self.user_id = None
        self.secret = None

        self.access_token = None
        self.refresh_token_val = None

    # 1. 用户登录
    def login(self, userName: str, password: str, apiKey: str) -> dict:
        url = f"{self.host}{self.base_path}/oauth/v3.0/userLogin"
        headers = {
            "Content-Type": "application/json",
            "Accept": "*/*"
        }
        body = {
            "userName": userName,
            "password": password,
            "apiKey": apiKey
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            result = resp.json()
            if result.get("flag") == "00":
                self.client_id = result.get("clientId")
                self.user_id = result.get("id")
                self.secret = result.get("secret")
            return result
        except Exception as e:
            return {"flag": "99", "msg": f"异常：{str(e)}"}

    # 2. 获取AccessToken
    def get_access_token(self, userName: str, password: str) -> dict:
        if not self.client_id or not self.secret:
            return {"flag": "99", "msg": "请先调用login()"}
        auth_str = f"{self.client_id}:{self.secret}"
        auth_b64 = base64.b64encode(auth_str.encode()).decode()
        url = f"{self.host}{self.base_path}/oauth/v3.0/getAccessToken"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {auth_b64}"
        }
        body = {"userName": userName, "password": password}
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            result = resp.json()
            if result.get("flag") == "00":
                self.access_token = result.get("accessToken")
                self.refresh_token_val = result.get("refreshToken")
            return result
        except Exception as e:
            return {"flag": "99", "msg": f"异常：{str(e)}"}

    # 3. 刷新Token
    def refresh_token(self) -> dict:
        if not self.client_id or not self.secret or not self.refresh_token_val:
            return {"flag": "99", "msg": "缺少参数，请先获取token"}
        url = f"{self.host}{self.base_path}/oauth/v3.0/refreshToken"
        headers = {"Content-Type": "application/json"}
        body = {
            "clientId": self.client_id,
            "clientSecret": self.secret,
            "refreshToken": self.refresh_token_val
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            result = resp.json()
            if result.get("flag") == "00":
                self.access_token = result.get("accessToken")
                self.refresh_token_val = result.get("refreshToken")
            return result
        except Exception as e:
            return {"flag": "99", "msg": f"异常：{str(e)}"}

    # 4. 获取用户信息
    def get_user_info(self) -> dict:
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/user/v3.0/getUserInfo"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {"userId": self.user_id}
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"异常：{str(e)}"}

    # 5. 分页获取设备(不含传感器)
    def get_devices(self, curr_page=1, page_size=100, group_id=None,
                    is_delete=None, is_line=None, is_alarms=None) -> dict:
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/device/v3.0/getDevices"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {
            "userId": self.user_id,
            "currPage": curr_page,
            "pageSize": page_size
        }
        if group_id is not None:
            body["groupId"] = group_id
        if is_delete is not None:
            body["isDelete"] = is_delete
        if is_line is not None:
            body["isLine"] = is_line
        if is_alarms is not None:
            body["isAlarms"] = is_alarms
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"异常：{str(e)}"}

    # 6. 分页获取设备(含传感器)
    def get_devices_sensor_datas(self, curr_page=1, page_size=100,
                                  group_id=None, is_delete=None,
                                  is_line=None, is_alarms=None) -> dict:
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/device/v3.0/getDevicesSensorDatas"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {
            "userId": self.user_id,
            "currPage": curr_page,
            "pageSize": page_size
        }
        if group_id is not None:
            body["groupId"] = group_id
        if is_delete is not None:
            body["isDelete"] = is_delete
        if is_line is not None:
            body["isLine"] = is_line
        if is_alarms is not None:
            body["isAlarms"] = is_alarms
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"异常：{str(e)}"}

    # 7. 获取单个设备数据
    def get_single_device_datas(self, device_id=None, device_no=None, curr_page=1, page_size=10):
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/device/v3.0/getSingleDeviceDatas"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {
            "userId": self.user_id,
            "currPage": curr_page,
            "pageSize": page_size
        }
        if device_id:
            body["deviceId"] = device_id
        if device_no:
            body["deviceNo"] = device_no
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"请求异常：{str(e)}"}

    # 8. 获取单个传感器数据
    def get_single_sensor_datas(self, sensor_id):
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/device/v3.0/getSingleSensorDatas"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {
            "userId": self.user_id,
            "sensorId": sensor_id
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"请求异常：{str(e)}"}

    # 9. 设备开关下行控制
    def switcher_controller(self, device_no: str, sensor_id: int, switcher: int) -> dict:
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/device/v3.0/switcherController"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {
            "userId": self.user_id,
            "deviceNo": device_no,
            "sensorId": sensor_id,
            "switcher": switcher
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"控制请求异常：{str(e)}"}

    # 10. 设备数据下行（数值写入）
    def device_write(self, device_no: str, sensor_id: int, value: str) -> dict:
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/device/v3.0/deviceWrite"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {
            "userId": self.user_id,
            "deviceNo": device_no,
            "sensorId": sensor_id,
            "value": value
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"数据下行异常：{str(e)}"}

    # ===================== 11. 获取传感器历史数据 =====================
    def get_sensor_history(self, sensor_id, start_date, end_date, page_size=100, paging_state=""):
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/device/v3.0/getSensorHistroy"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {
            "userId": self.user_id,
            "sensorId": sensor_id,
            "startDate": start_date,
            "endDate": end_date,
            "pageSize": page_size,
            "pagingState": paging_state
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"获取历史数据异常：{str(e)}"}

    # ===================== 12. 获取设备分组 =====================
    def get_device_group(self):
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/device/v3.0/getDeviceGroup"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {"userId": self.user_id}
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"获取设备分组异常：{str(e)}"}

    # ===================== 13. 获取传感器历史平均值 =====================
    def get_sensor_history_avg(self, sensor_id, start_date, end_date, 
                               data_type="day", is_asc=True, page_size=100, paging_state=""):
        if not self.access_token:
            return {"flag": "99", "msg": "请先get_access_token()"}
        url = f"{self.host}{self.base_path}/device/v3.0/getSensorHistroyAvg"
        headers = {
            "Content-Type": "application/json",
            "ClientId": self.client_id,
            "Authorization": f"Bearer {self.access_token}"
        }
        body = {
            "userId": self.user_id,
            "sensorId": sensor_id,
            "startDate": start_date,
            "endDate": end_date,
            "type": data_type,
            "isAsc": is_asc,
            "pageSize": page_size,
            "pagingState": paging_state
        }
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=30)
            return resp.json()
        except Exception as e:
            return {"flag": "99", "msg": f"获取历史平均值异常：{str(e)}"}


# ===================== 测试入口=====================
if __name__ == "__main__":
    from config import USERNAME, PASSWORD, API_KEY

    if not all([USERNAME, PASSWORD, API_KEY]):
        raise SystemExit("请先配置 IOT_USERNAME、IOT_PASSWORD 和 IOT_API_KEY 后再运行测试入口。")

    client = IotClient()

    login_res = client.login(
        userName=USERNAME,
        password=PASSWORD,
        apiKey=API_KEY
    )
    print("登录结果：", login_res)

    if login_res.get("flag") == "00":
        token_res = client.get_access_token(USERNAME, PASSWORD)
        print("\n获取Token结果：", token_res)

        if token_res.get("flag") == "00":
            refresh_res = client.refresh_token()
            print("\n刷新Token结果：", refresh_res)

            user_info = client.get_user_info()
            print("\n用户信息：", user_info)

            devices = client.get_devices(curr_page=1, page_size=10)
            with open("devices.json", "w", encoding="utf-8") as f:
                json.dump(devices, f, ensure_ascii=False, indent=4)
            print("\n设备列表(不含传感器)：", devices)
            
            devices_sensor = client.get_devices_sensor_datas()
            print("\n设备列表(含传感器)：", devices_sensor)
            with open("devices_sensor.json", "w", encoding="utf-8") as f:
                json.dump(devices_sensor, f, ensure_ascii=False, indent=4)

            single_device = client.get_single_device_datas(
                device_id=787178386104645,
                curr_page=1,
                page_size=10
            )
            print("\n 单个设备数据：", single_device)

            single_sensor = client.get_single_sensor_datas(sensor_id=787178386121029)
            print("\n 单个传感器数据：", single_sensor)

            # 开关控制（现场再用）
            # ctrl_res = client.switcher_controller(
            #     device_no="HJZNQHNLWLW00001",
            #     sensor_id=787178386121029,
            #     switcher=1
            # )
            # print("\n 开关控制结果：", ctrl_res)

            # 设备数据下行（数值写入，现场再用）
            # write_res = client.device_write(
            #     device_no="HJZNQHNLWLW00001",
            #     sensor_id=787178386121029,
            #     value="50"  # 要下发的数值
            # )
            # print("\n 数据下行结果：", write_res)

            #  1. 获取设备分组
            group_data = client.get_device_group()
            print("\n 设备分组：", group_data)

            #  2. 获取传感器历史数据
            history_data = client.get_sensor_history(
                sensor_id=787178386121029,
                start_date="2026-05-06 00:00:00",
                end_date="2026-05-07 23:59:59",
                page_size=20
            )
            print("\n 传感器历史数据：", history_data)

            #  3. 获取传感器历史平均值（按天）
            avg_data = client.get_sensor_history_avg(
                sensor_id=787178386121029,
                start_date="2026-05-01 00:00:00",
                end_date="2026-05-07 23:59:59",
                data_type="day"  # minute / hour / day / week
            )
            print("\n 传感器历史平均值：", avg_data)
        
            # 数据下载申请
            # apply_res = client.data_download_apply(
            #     device_id=787178386104645,
            #     start_time="2026-05-01 00:00:00",
            #     end_time="2026-05-07 23:59:59",
            #     remark="历史数据导出"
            # )
            # print(apply_res)

            # 获取数据下载列表
            # list_res = client.data_download_list(curr_page=1, page_size=10)
            # print(list_res)

            # 删除数据下载记录
            # del_res = client.data_download_delete(data_download_id=123456)
            # print(del_res)
     
    
