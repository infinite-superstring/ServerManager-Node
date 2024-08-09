import asyncio
import json
import os
import platform
import time
from datetime import datetime
from threading import Thread

import aiohttp
import psutil
from psutil import AccessDenied

from utils.logger import logger
import utils.websocket as WebSocket
from utils.processUtils import kill_proc_tree

# import main

get_process_list_flag: bool = False
get_process_list_thread: Thread


@logger.catch
async def get_disk_list():
    disk_list = []
    for item in psutil.disk_partitions():
        total = 0
        used = 0
        try:
            total = psutil.disk_usage(item.mountpoint).total
            used = psutil.disk_usage(item.mountpoint).used
        except Exception:
            pass
        disk_list.append({
            "device": item.device,
            "mount_point": item.mountpoint,
            "fs_type": item.fstype,
            "total": total,
            "used": used
        })
    return disk_list


@logger.catch
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
        "memory_total": psutil.virtual_memory().total,
        "disks": await get_disk_list(),
        "hostname": platform.node(),
        "boot_time": datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        await ws.websocket_send_json({'action': 'node:refresh_info', 'data': node_info})
    except Exception as e:
        logger.error(f"节点信息更新上传失败！{e}")


@logger.catch
async def get_disk_io_counters(time: int = 1):
    """获取磁盘io计数器/秒"""
    # 获取初始时刻的IO计数器值
    io_counters_start = psutil.disk_io_counters()
    # 等待一段时间
    try:
        await asyncio.sleep(time)
    except asyncio.exceptions.CancelledError:
        pass
    # 获取结束时刻的IO计数器值
    io_counters_end = psutil.disk_io_counters()
    read_bytes = io_counters_end.read_bytes - io_counters_start.read_bytes
    write_bytes = io_counters_end.write_bytes - io_counters_start.write_bytes
    return {"read_bytes": read_bytes, "write_bytes": write_bytes}


@logger.catch
async def get_network_io_counters(time: int = 1):
    """获取网络io计数器/秒"""
    # 获取初始时刻的IO计数器值
    network_counters_start = psutil.net_io_counters(pernic=True)
    all_network_counters_start = psutil.net_io_counters()
    # 等待一段时间
    try:
        await asyncio.sleep(time)
    except asyncio.exceptions.CancelledError:
        pass
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


@logger.catch
async def update_node_usage(ws: WebSocket):
    """更新节点占用状态"""
    node_core_usage = psutil.cpu_percent(percpu=True)
    node_cpu_usage = psutil.cpu_percent()
    node_memory = psutil.virtual_memory()
    node_loadavg = psutil.getloadavg()
    node_swap = psutil.swap_memory()
    node_disk_io = await get_disk_io_counters()
    node_network_io = await get_network_io_counters()
    if not node_disk_io or not node_network_io:
        return
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
            'partition_list': await get_disk_list(),
        },
        "network": {
            "io": node_network_io
        }
    }
    await ws.websocket_send_json({'action': 'node:upload_running_data', 'data': node_usage})


@logger.catch
async def start_get_process_list(ws: WebSocket):
    global get_process_list_flag
    """获取节点进程列表"""
    if not get_process_list_flag:
        logger.debug('服务端发起获取进程列表')
        get_process_list_thread = Thread(target=get_process_list, args=(ws,))
        get_process_list_thread.start()


@logger.catch
async def stop_get_process_list():
    global get_process_list_flag
    if get_process_list_flag:
        get_process_list_flag = False
        logger.debug("服务端停止获取进程列表")


@logger.catch
async def kill_process(pid, tree_mode):
    logger.warning("kill_process")
    if pid == os.getpid():
        return logger.error("won't kill myself")
    if psutil.pid_exists(pid) and not tree_mode:
        try:
            psutil.Process(pid).kill()
        except Exception as e:
            logger.error(e)
    elif psutil.pid_exists(pid) and tree_mode:
        try:
            kill_proc_tree(pid)
        except Exception as e:
            logger.error(e)
    else:
        RuntimeError(f"Process {pid} does not exist")


@logger.catch
def get_process_list(ws: WebSocket):
    global get_process_list_flag
    get_process_list_flag = True
    logger.debug("获取进程列表进程已启动.....")
    while get_process_list_flag:
        try:
            temp = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'status', 'cpu_percent', 'memory_info']):
                info = proc.info
                temp.append({
                    "pid": info.get("pid"),
                    "name": info.get("name"),
                    "username": info.get("username"),
                    "status": info.get("status"),
                    "cpu_percent": round(info.get("cpu_percent") / psutil.cpu_count(), 1),
                    "memory_usage": round((info.get("memory_info").rss / psutil.virtual_memory().total) * 100, 1),
                    "swap_usage": info.get("memory_info").vms
                })
        except AccessDenied:
            logger.warning("无权限获取进程列表，请检查是否已用root用户运行")
            get_process_list_flag = False
        else:
            asyncio.run(
                ws.websocket_send_json({'action': 'process_list:show', 'data': {
                    'process_list': temp,
                }})
            )
        time.sleep(5)
    logger.debug("获取进程列表进程已停止")
