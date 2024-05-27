import asyncio
import json

import aiohttp
from aiohttp import web, ClientWebSocketResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.auth import authenticate
from utils.logger import logger
from utils.node import update_node_usage, update_node_info
from utils.tty import tty_service


class WebSocket:
    __session: aiohttp.ClientSession
    __ws: aiohttp.client_ws.ClientWebSocketResponse
    __scheduler: AsyncIOScheduler = None
    __node_config: dict
    __tty_service: tty_service = None

    def __init__(self, session: aiohttp.ClientSession):
        self.__session = session
        self.__scheduler = AsyncIOScheduler()
        self.__tty_service = tty_service()

    async def websocket_connect(self):
        from utils.config import config
        config = config().get_config
        SSL = config().get('server').get('enable_SSL')
        host = config().get('server').get('server_host')
        port = config().get('server').get('server_port')
        ws_url = ("wws://" if SSL else "ws://" + host + ":" + str(port) + "/ws/node/node_client")
        auth_path = f'{"https" if SSL else "http"}://{host}:{port}/api/auth/nodeAuth'
        auth_data = {
            "server_token": config()['server']['server_token'],
            "node_name": config()['server']['client_name'],
            "node_token": config()['server']['client_token'],
        }
        while True:
            try:
                # 发送节点认证请求
                self.__session = await authenticate(self.__session, auth_path, auth_data)
                async with self.__session.ws_connect(ws_url, autoping=True) as ws:
                    self.__ws = ws
                    recv_task = asyncio.create_task(self.message_handler())
                    await update_node_info(self)
                    await recv_task
            except aiohttp.ClientError:
                print("WebSocket connection failed. Retrying...")
                await asyncio.sleep(5)
            if self.__scheduler and self.__scheduler.state != 0:
                self.__scheduler.shutdown()
            self.__tty_service.close()

    async def message_handler(self):
        while not self.__ws.closed:
            msg: aiohttp.http_websocket.WSMessage = await self.__ws.receive()
            match msg.type:
                case web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    print(data)
                    if data.get('action'):
                        match data['action']:
                            # 关闭节点端
                            case 'close':
                                logger.info(f'Close......')
                                self.__scheduler.shutdown()
                                return
                            # 初始化节点配置
                            case 'init_node_config':
                                logger.info(f'Init node config....')
                                self.__node_config = data['data']
                                # 添加调度任务
                                # 调度方法为 update_node_usage，触发器选择 interval(间隔性)，间隔时长为 2 秒
                                self.__scheduler.add_job(
                                    update_node_usage,
                                    'interval',
                                    seconds=self.__node_config['upload_data_interval'],
                                    args=[self]
                                )
                                # 启动调度任务
                                self.__scheduler.start()
                            # 初始化虚拟终端
                            case "init_terminal":
                                index = data['data']['index']
                                tty_session_uuid = self.__tty_service.create_session()
                                logger.debug(f"inti tty succeed; session uuid: {tty_session_uuid}")
                                await self.websocket_send_json({
                                    "action": "create_terminal_session",
                                    "data": {
                                        "uuid": tty_session_uuid,
                                        "index": index
                                    }
                                })
                                self.__tty_service.terminal_output(tty_session_uuid, self)
                            case "close_terminal":
                                tty_session_uuid = data['data']['uuid']
                                await self.__tty_service.close_session(tty_session_uuid)
                            case _:
                                logger.error(f'未定义的操作: {data["action"]}')
                case web.WSMsgType.BINARY:
                    pass
                case web.WSMsgType.CLOSE:
                    self.__scheduler.shutdown()
                    logger.info("连接已断开，程序退出")
                    # exit(1)
            await asyncio.sleep(0.2)

    async def websocket_send_json(self, data: dict):
        try:
            await self.__ws.send_str(json.dumps(data))
        except ConnectionResetError as e:
            logger.error(e)
            self.__scheduler.shutdown(wait=False)
            await self.__ws.close()
            logger.info('Stop WebSocket...')
