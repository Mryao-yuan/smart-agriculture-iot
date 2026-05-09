import re



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