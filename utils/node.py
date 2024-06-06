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
    """更新节点信息"""
    node_info = {
        "system": platform.system(),
        "system_release": platform.release(),
        "system_build_version": platform.version(),
        "cpu": {
            "architecture": platform.machine(),
            "processor": psutil.cpu_count(),
            "core": psutil.cpu_count(logical=False)
        },
        "disks": [{"device": i.device, "mount_point": i.mountpoint, "fs_type": i.fstype,
                   "total": psutil.disk_usage(i.device).total, "used": psutil.disk_usage(i.mountpoint).used} for i in
                  psutil.disk_partitions()],
        "hostname": platform.node(),
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        pass
        await ws.websocket_send_json({'action': 'refresh_node_info', 'data': node_info})
    except Exception as e:
        logger.error(f"节点信息更新失败！\n{e}")


async def get_disk_io_counters(time: int = 1):
    """获取磁盘io计数器/秒"""
    # 获取初始时刻的IO计数器值
    io_counters_start = psutil.disk_io_counters()
    # 等待一段时间
    await asyncio.sleep(time)
    # 获取结束时刻的IO计数器值
    io_counters_end = psutil.disk_io_counters()
    read_bytes = io_counters_end.read_bytes - io_counters_start.read_bytes
    write_bytes = io_counters_end.write_bytes - io_counters_start.write_bytes
    return {"read_bytes": read_bytes, "write_bytes": write_bytes}


async def get_network_io_counters(time: int = 1):
    """获取网络io计数器/秒"""
    # 获取初始时刻的IO计数器值
    network_counters_start = psutil.net_io_counters(pernic=True)
    all_network_counters_start = psutil.net_io_counters()
    # 等待一段时间
    await asyncio.sleep(time)
    # 获取结束时刻的IO计数器值
    network_counters_end = psutil.net_io_counters(pernic=True)
    all_network_counters_end = psutil.net_io_counters()
    temp = {
        "_all": {
            "bytes_sent": all_network_counters_end.bytes_sent - all_network_counters_start.bytes_sent,
            "bytes_recv": all_network_counters_end.bytes_recv - all_network_counters_start.bytes_recv,
        }
    }
    for key in network_counters_start:
        temp[key] = {
            "bytes_sent": network_counters_end[key].bytes_sent - network_counters_start[key].bytes_sent,
            "bytes_recv": network_counters_end[key].bytes_recv - network_counters_start[key].bytes_recv,
        }
    return temp


async def update_node_usage(ws: WebSocket):
    """更新节点占用状态"""
    node_core_usage = psutil.cpu_percent(percpu=True)
    node_cpu_usage = psutil.cpu_percent()
    node_memory = psutil.virtual_memory()
    node_loadavg = psutil.getloadavg()
    node_swap = psutil.swap_memory()
    node_disk_io = await get_disk_io_counters()
    node_network_io = await get_network_io_counters()
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
            "io": node_disk_io,
            'partition_list': [
                {
                    "device": i.device,
                    "mount_point": i.mountpoint,
                    "fs_type": i.fstype,
                    "total": psutil.disk_usage(i.device).total,
                    "used": psutil.disk_usage(i.mountpoint).used
                } for i in psutil.disk_partitions()
            ]
        },
        "network": {
            "io": node_network_io
        }
    }
    await ws.websocket_send_json({'action': 'upload_running_data', 'data': node_usage})


async def get_process_list(ws: WebSocket, index: str = None):
    """获取节点进程列表"""
    temp = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_info']):
        info = proc.info
        temp.append({
            "pid": info.get("pid"),
            "name": info.get("name"),
            "username": info.get("username"),
            "status": info.get("status"),
            "cpu_percent": info.get("cpu_percent"),
            "memory_usage": info.get("memory_info").rss,
            "swap_usage": info.get("memory_info").vms
        })
    await ws.websocket_send_json({'action': 'get_process_list', 'data': {
        'process_list': temp,
        'index': index
    }})
