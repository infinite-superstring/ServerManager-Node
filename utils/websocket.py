import asyncio
import json

import aiohttp
from aiohttp import web, ClientWebSocketResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.auth import authenticate
from utils.logger import logger
from utils.node import update_node_usage, update_node_info, get_process_list, start_get_process_list, \
    stop_get_process_list, kill_process
from utils.tty import tty_service


class WebSocket:
    __session: aiohttp.ClientSession
    __ws: aiohttp.client_ws.ClientWebSocketResponse
    __update_node_usage_scheduler: AsyncIOScheduler = None
    __get_process_list_scheduler: AsyncIOScheduler = None
    __node_config: dict
    __tty_service: tty_service = None
    __config = None

    def __init__(self, session: aiohttp.ClientSession):
        self.__session = session
        self.__update_node_usage_scheduler = AsyncIOScheduler()
        self.__get_process_list_scheduler = AsyncIOScheduler()
        self.__tty_service = tty_service()

    async def websocket_connect(self):
        from utils.config import config
        self.__config = config().get_config
        SSL = self.__config().get('server').get('enable_SSL')
        host = self.__config().get('server').get('server_host')
        port = self.__config().get('server').get('server_port')
        ws_url = ("wws://" if SSL else "ws://" + host + ":" + str(port) + "/ws/node/node_client")
        auth_path = f'{"https" if SSL else "http"}://{host}:{port}/api/auth/nodeAuth'
        auth_data = {
            "server_token": self.__config()['server']['server_token'],
            "node_name": self.__config()['server']['client_name'],
            "node_token": self.__config()['server']['client_token'],
        }
        while True:
            try:
                # 发送节点认证请求
                self.__session = await authenticate(self.__session, auth_path, auth_data)
                async with self.__session.ws_connect(ws_url, autoping=True) as ws:
                    self.__ws = ws
                    recv_task = asyncio.create_task(self.message_handler())
                    await recv_task
            except aiohttp.ClientError as err:
                logger.error(f"WebSocket connection failed. Retrying...({err})")
                await asyncio.sleep(5)
            if self.__update_node_usage_scheduler and self.__update_node_usage_scheduler.state != 0:
                self.__update_node_usage_scheduler.shutdown()
                self.__update_node_usage_scheduler.shutdown()
            self.__tty_service.close()

    async def message_handler(self):
        while not self.__ws.closed:
            msg: aiohttp.http_websocket.WSMessage = await self.__ws.receive()
            match msg.type:
                case web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    print(data)
                    if not data.get('action'):
                        return
                    match data['action']:
                        # 关闭节点端
                        case 'close':
                            logger.info(f'Close......')
                            self.__update_node_usage_scheduler.shutdown()
                            self.__get_process_list_scheduler.shutdown()
                            await stop_get_process_list()
                            return exit(0)
                        # 初始化节点配置
                        case 'init_node_config':
                            logger.info(f'Init node config....')
                            await update_node_info(self)
                            self.__node_config = data['data']
                            # 添加调度任务
                            # 调度方法为 update_node_usage，触发器选择 interval(间隔性)，间隔时长为 2 秒
                            self.__update_node_usage_scheduler.add_job(
                                update_node_usage,
                                'interval',
                                seconds=self.__node_config['upload_data_interval'],
                                args=[self]
                            )
                            # 启动调度任务
                            self.__update_node_usage_scheduler.start()
                        # 初始化虚拟终端
                        case "terminal:create_session":
                            index = data['data']['index']
                            host = data['data']['host']
                            port = data['data']['port']
                            username = data['data']['username']
                            password = data['data']['password']
                            if self.__config().get("safe").get("connect_terminal"):
                                tty_session_uuid = self.__tty_service.create_session(host, port, username, password)
                                logger.debug(f"inti tty succeed; session uuid: {tty_session_uuid}")
                                await self.websocket_send_json({
                                    "action": "terminal:return_session",
                                    "data": {
                                        "uuid": tty_session_uuid,
                                        "index": index
                                    }
                                })
                                self.__tty_service.terminal_output(tty_session_uuid, self)
                            else:
                                await self.websocket_send_json({
                                    "action": "safe:Terminal_not_enabled",
                                    "msg": "终端连接未启用",
                                    "data": {
                                        "index": index
                                    }
                                })
                        case "terminal:close_session":
                            tty_session_uuid = data['data']['uuid']
                            self.__tty_service.close_session(tty_session_uuid)
                        case "terminal:input":
                            command = data['data']['command']
                            tty_session_uuid = data['data']['uuid']
                            self.__tty_service.send_command(tty_session_uuid, command)
                        case "process_list:start":
                            await start_get_process_list(self)
                        case "process_list:stop":
                            await stop_get_process_list()
                        case "process_list:kill":
                            pid = data['data']['pid']
                            tree_mode = data['data'].get('tree_mode', False)
                            if pid:
                                await kill_process(pid, tree_mode)
                        case _:
                            logger.error(f'未定义的操作: {data["action"]}')
                case web.WSMsgType.BINARY:
                    pass
                case web.WSMsgType.CLOSE:
                    self.__update_node_usage_scheduler.shutdown()
                    self.__update_node_usage_scheduler.shutdown()
                    logger.info("连接已断开")
            await asyncio.sleep(0.2)

    async def websocket_send_json(self, data: dict):
        try:
            await self.__ws.send_str(json.dumps(data))
        except ConnectionResetError as e:
            logger.error(e)
            self.__update_node_usage_scheduler.shutdown(wait=False)
            self.__update_node_usage_scheduler.shutdown(wait=False)
            await stop_get_process_list()
            await self.__ws.close()
            logger.info('Stop WebSocket...')
