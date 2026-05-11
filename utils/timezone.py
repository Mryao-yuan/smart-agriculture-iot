from datetime import datetime
from zoneinfo import ZoneInfo

APP_TIMEZONE = ZoneInfo("Asia/Shanghai")

def get_local_now():
    """
    返回按业务时区（北京时间）计算的当前时间。
    为兼容现有大量 naive datetime 逻辑，这里返回去掉 tzinfo 的本地时间。
    """
    return datetime.now(APP_TIMEZONE).replace(tzinfo=None)
