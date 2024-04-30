import json

import psutil

print(psutil.cpu_times())
print(psutil.swap_memory())

cpu_usage = psutil.cpu_percent()

print("当前CPU使用率：%f%%" % cpu_usage)

node_memory = psutil.virtual_memory()
node_swap = psutil.swap_memory()
node_usage = {
    "cpu": {
        "": ""
    },
    "memory": {
        # 总量
        "total": node_memory.total,
        # 可用
        "available": node_memory.available,
        # 已用
        "used": node_memory.used,
        # 使用率
        "percent": node_memory,
    },
    "swap": {
        # 总量
        "total": node_swap.total,
        # 使用中
        "used": node_swap.used,
        # 可用的
        "free": node_swap.free,
        # 使用率
        "percent": node_swap.percent
    },
    "disk": psutil.disk_io_counters(perdisk=True),
    "network": {
        "io_counters": psutil.net_io_counters(pernic=True),
        "addrs": psutil.net_if_addrs()
    }
}

print(node_usage)