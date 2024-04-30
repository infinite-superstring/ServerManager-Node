import asyncio
import json
import os
from os import path

import aiohttp
from threading import Thread
from aiohttp import web
from aiohttp.client_ws import ClientWebSocketResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from utils.config import config
from utils.logger import logger
from utils.node import update_node_info, update_node_usage

config = config().get_config
# 创建后台执行的 schedulers
scheduler = AsyncIOScheduler()

async def message_handler(ws: ClientWebSocketResponse):
    while True:
        # msg: <class 'aiohttp.http_websocket.WSMessage'>
        msg = await ws.receive()
        if msg.type == web.WSMsgType.TEXT:
            data = json.loads(msg.data)
            if data.get('action'):
                match data['action']:
                    case 'close':
                        logger.info(f'Close......')
                        exit(0)
                        pass
                    case _:
                        logger.error(f'未定义的操作: {data["action"]}')
        elif msg.type == web.WSMsgType.BINARY:
            print("RECV:", msg.data)
        elif msg.type == web.WSMsgType.PING:
            print("RECV: PING")
            await ws.pong()  # 收到 PING 后给服务端回复 PONG
        elif msg.type == web.WSMsgType.PONG:
            print("RECV: PONG")
        elif msg.type == web.WSMsgType.CLOSE:
            print("RECV: CLOSE")
        else:
            print("RECV:", msg)
        await asyncio.sleep(2)


async def main():
    async with aiohttp.ClientSession() as session:
        SSL = config().get('server').get('enable_SSL')
        host = config().get('server').get('server_host')
        port = config().get('server').get('server_port')
        ws_path = config().get('server').get('server_path')
        ws_url = ("wws://" if SSL else "ws://" + host + ":" + str(port) + ws_path)
        auth_path = f'{"https" if SSL else "http"}://{host}:{port}/node/auth'
        auth_data = {
            "action": "auth",
            "data": {
                "server_token": config()['server']['server_token'],
                "client_name": config()['server']['client_name'],
                "client_token": config()['server']['client_token'],
            }
        }
        server_config: dict

        # async with session.post(auth_path, json=auth_data) as resp:
        #     try:
        #         data = await resp.json()
        #         if data['status'] == 1:
        #             logger.info(f'认证成功')
        #             server_config = data.get('data').get('config')
        #         else:
        #             logger.error(f"认证失败: {data['mgs']}({data['status']})")
        #             exit(1)
        #     except Exception as e:
        #         logger.error(f"服务端返回了无效消息：\n{await resp.text()}(http code:{resp.status})")
        #         exit(1)

        logger.info(f'连接到Websocket: {ws_url}')
        async with session.ws_connect(ws_url, autoping=True) as ws:
            # ws: <class 'aiohttp.client_ws.ClientWebSocketResponse'>
            # 异步 循环接收消息
            recv_task = asyncio.create_task(message_handler(ws))

            await update_node_info(ws)

            # 添加调度任务
            # 调度方法为 timedTask，触发器选择 interval(间隔性)，间隔时长为 2 秒
            # scheduler.add_job(update_node_usage(ws), 'interval', seconds=server_config['interval'])
            scheduler.add_job(update_node_usage, 'interval', seconds=1, args=[ws])
            # 启动调度任务
            scheduler.start()

            await recv_task


asyncio.run(main())
