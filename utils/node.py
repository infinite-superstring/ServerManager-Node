import asyncio
import json
import platform
from datetime import datetime

import aiohttp
import psutil

from utils.logger import logger
import utils.websocket as WebSocket


# import main


async def update_node_info(ws: WebSocket):
    node_info = {
        "system": platform.system(),
        "system_release": platform.release(),
        "system_build_version": platform.version(),
        "cpu": {
            "architecture": platform.machine(),
            "processor": psutil.cpu_count(),
            "core": psutil.cpu_count(logical=False)
        },
        "disks": [{"device": i.device, "mount_point": i.mountpoint, "fs_type": i.fstype, "total": psutil.disk_usage(i.device).total} for i in psutil.disk_partitions()],
        "hostname": platform.node(),
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        pass
        await ws.websocket_send_json({'action': 'refresh_node_info', 'data': node_info})
    except Exception as e:
        logger.error(f"节点信息更新失败！\n{e}")


async def update_node_usage(ws: WebSocket):
    node_core_usage = psutil.cpu_percent(percpu=True)
    node_cpu_usage = psutil.cpu_percent()
    node_memory = psutil.virtual_memory()
    node_loadavg = psutil.getloadavg()
    node_swap = psutil.swap_memory()
    # 获取初始时刻的IO计数器值
    io_counters_start = psutil.disk_io_counters()
    # 等待一段时间
    await asyncio.sleep(1)
    # 获取结束时刻的IO计数器值
    io_counters_end = psutil.disk_io_counters()
    node_usage = {
        "loadavg": node_loadavg,
        "cpu": {
            "usage": node_cpu_usage,
            "core_usage": node_core_usage,
        },
        "memory": {
            # 总量
            "total": node_memory.total,
            # 已用
            "used": node_memory.used,
        },
        "swap": {
            # 总量
            "total": node_swap.total,
            # 使用中
            "used": node_swap.used,
        },
        "disk": {
            "io": {
                "read_bytes": io_counters_end.read_bytes - io_counters_start.read_bytes,
                "write_bytes": io_counters_end.write_bytes - io_counters_start.write_bytes
            },
            'partition_list': [{"device": i.device, "mount_point": i.mountpoint, "fs_type": i.fstype, "total": psutil.disk_usage(i.device).total} for i in psutil.disk_partitions()]
        }
    }
    await ws.websocket_send_json({'action': 'upload_running_data', 'data': node_usage})
