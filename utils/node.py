import json
import platform

import aiohttp
import psutil

from utils.logger import logger


async def update_node_info(ws: aiohttp.client_ws.ClientWebSocketResponse):
    node_info = {
        "system": platform.system(),
        "system_release": platform.release(),
        "system_build_version": platform.version(),
        "cpu": {
            "architecture": platform.machine(),
            "threads": psutil.cpu_count(),
            "cores": psutil.cpu_count(logical=False)
        },
        "memory": psutil.virtual_memory().total,
        "hostname": platform.node(),
        "boot_time": psutil.boot_time()
    }
    try:
        await ws.send_str(json.dumps(node_info))
    except Exception as e:
        logger.error(f"节点信息更新失败！\n{e}")


async def update_node_usage(ws: aiohttp.client_ws.ClientWebSocketResponse):
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
            "port_info": psutil.net_if_addrs()
        }
    }
    await ws.send_str(json.dumps(node_usage))
