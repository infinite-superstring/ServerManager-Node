import asyncio
import json
import os.path
import time

import aiohttp
from aiohttp import web, ClientWebSocketResponse
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from utils.auth import authenticate
from utils.logger import logger
from utils.node import update_node_usage, update_node_info, start_get_process_list, \
    stop_get_process_list, kill_process
from utils.tty import tty_service
from utils.shellTaskUtils import shellTaskUtils
from utils.executeUtils import executeUtils


class WebSocket:
    __session: aiohttp.ClientSession
    __ws: aiohttp.client_ws.ClientWebSocketResponse
    __scheduler: AsyncIOScheduler = None
    __node_config: dict
    __tty_service: tty_service = None
    __shell_task_service: shellTaskUtils = None
    __shell_execute_service: executeUtils = None
    __config = None
    __data_path: str

    def __init__(self, session: aiohttp.ClientSession):
        # 初始化数据存储路径
        self.__data_path = os.path.join(os.getcwd(), "data")
        if not os.path.exists(self.__data_path):
            os.mkdir(self.__data_path)
        self.__session = session

    async def websocket_connect(self):
        from utils.config import config
        self.__config = config().get_config
        SSL = self.__config().get('server').get('enable_SSL')
        host = self.__config().get('server').get('server_host')
        port = self.__config().get('server').get('server_port')
        ws_url = ("wws://" if SSL else "ws://" + host + ":" + str(port) + "/ws/node/node_client")
        auth_path = f'{"https" if SSL else "http"}://{host}:{port}/api/auth/nodeAuth'
        auth_data = {
            "node_name": self.__config()['server']['client_name'],
            "node_token": self.__config()['server']['client_token'],
        }
        while True:
            try:
                # 发送节点认证请求
                self.__session, auth_status = await authenticate(self.__session, auth_path, auth_data)
                if not auth_status:
                    time.sleep(5)
                    continue
                self.__tty_service = tty_service()
                self.__shell_task_service = shellTaskUtils(self)
                self.__shell_execute_service = executeUtils(self)
                self.__scheduler = AsyncIOScheduler()
                async with self.__session.ws_connect(ws_url, autoping=True) as ws:
                    logger.success("WebSocket已连接")
                    self.__ws = ws
                    recv_task = asyncio.create_task(self.message_handler())
                    await recv_task
            except aiohttp.ClientError as err:
                logger.error(f"WebSocket connection failed. Retrying...({err})")
            finally:
                await asyncio.sleep(5)
            await stop_get_process_list()
            if self.__scheduler and self.__scheduler.state != 0:
                self.__scheduler.shutdown(wait=False)
            if self.__shell_task_service:
                self.__shell_task_service.close()
                del self.__shell_task_service
            if self.__tty_service:
                del self.__tty_service


    async def message_handler(self):
        while not self.__ws.closed:
            msg: aiohttp.http_websocket.WSMessage = await self.__ws.receive()
            match msg.type:
                case web.WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    action = data.get('action')
                    logger.debug(f"action:{action} data:{data.get('data')}")
                    actions = {
                        "node:close": self._close,
                        "node:init_config": self._init_node_config,
                        "terminal:create_session": self._terminal__create_session,
                        "terminal:close_session": self._terminal__close_session,
                        "terminal:input": self._terminal__input,
                        "terminal:resize": self._terminal__resize,
                        "process_list:start": self._process_list__start,
                        "process_list:stop": self._process_list__stop,
                        "process_list:kill": self._process_list__kill,
                        "task:add": self._add_task,
                        "task:remove": self._remove_task,
                        "task:reload": self._reload_task,
                        "run_shell": self._execute_shell
                    }

                    if action not in actions.keys():
                        logger.error(f"Undefined action: {action}")
                        return
                    await actions[action](data.get('data'))
                case web.WSMsgType.BINARY:
                    pass
                case web.WSMsgType.CLOSE:
                    self.__scheduler.shutdown()
                    del self.__tty_service
                    del self.__shell_task_service
                    logger.info("连接已断开")
            # await asyncio.sleep(0.2)

    async def _close(self, payload=None):
        """关闭节点端"""
        logger.info(f'Close......')
        self.__scheduler.shutdown()
        await stop_get_process_list()
        return exit(0)

    async def _init_node_config(self, payload=None):
        """初始化节点配置"""
        logger.debug(f'Init node config....')
        await update_node_info(self)
        self.__node_config = payload
        await self._start_node_usage_upload_task()
        # 加载任务列表
        self.__shell_task_service.init_task_list(self.__node_config.get('task'))
        logger.info("node ready!")

    @logger.catch
    async def _terminal__create_session(self, payload=None):
        """创建终端Session"""
        index = payload['index']
        host = payload['host']
        port = payload['port']
        username = payload['username']
        password = payload['password']
        if self.__config().get("safe").get("connect_terminal") is False:
            await self.websocket_send_json({
                "action": "safe:Terminal_not_enabled",
                "msg": "终端连接未启用",
                "data": {
                    "index": index
                }
            })
        tty_session_uuid, login_status = self.__tty_service.create_session(host, port, username, password)
        if login_status:
            logger.debug(f"inti tty succeed; session uuid: {tty_session_uuid}")
            await self.websocket_send_json({
                "action": "terminal:return_session",
                "data": {
                    "uuid": tty_session_uuid,
                    "index": index
                }
            })
            # 获取终端输出
            self.__tty_service.terminal_output(tty_session_uuid, self)
            return
        await self.websocket_send_json({
            "action": "terminal:login_failed",
            "data": {
                "index": index
            }
        })

    @logger.catch
    async def _terminal__close_session(self, payload=None):
        """关闭终端会话"""
        tty_session_uuid = payload['uuid']
        self.__tty_service.close_session(tty_session_uuid)

    @logger.catch
    async def _terminal__input(self, payload=None):
        """向终端发送信息"""
        command = payload['command']
        tty_session_uuid = payload['uuid']
        self.__tty_service.send_command(tty_session_uuid, command)

    @logger.catch
    async def _terminal__resize(self, payload=None):
        """调整节点终端大小"""
        cols = payload['cols']
        rows = payload['rows']
        tty_session_uuid = payload['uuid']
        self.__tty_service.resize(tty_session_uuid, cols, rows)

    @logger.catch
    async def _process_list__start(self, payload=None):
        """开始获取进程列表"""
        await start_get_process_list(self)

    @logger.catch
    async def _process_list__stop(self, payload=None):
        """停止获取节点列表"""
        await stop_get_process_list()

    @logger.catch
    async def _process_list__kill(self, payload=None):
        """杀死一个进程"""
        pid = payload['pid']
        tree_mode = payload.get('tree_mode', False)
        if pid:
            await kill_process(pid, tree_mode)

    @logger.catch
    async def _start_node_usage_upload_task(self):
        """启动调度器：上传节点状态"""
        # 调度方法为 update_node_usage，触发器选择 interval(间隔性)，间隔时长为 2 秒
        self.__scheduler.add_job(
            update_node_usage,
            'interval',
            seconds=self.__node_config['upload_data_interval'],
            args=[self]
        )
        # 启动调度任务
        self.__scheduler.start()

    @logger.catch
    async def _add_task(self, data: dict):
        """添加任务"""
        self.__shell_task_service.add_task(data)

    @logger.catch
    async def _remove_task(self, data):
        """删除一个任务"""
        self.__shell_task_service.remove_task(data)

    @logger.catch
    async def _reload_task(self, data):
        """重载一个任务"""
        self.__shell_task_service.reload_task(data)

    @logger.catch
    async def _execute_shell(self, data):
        """执行一个shell"""
        self.__shell_execute_service.executeShellCommand(
            data.get('task_uuid'),
            data.get('base_path'),
            data.get("command"),
        )

    @logger.catch
    async def websocket_send_json(self, data: dict):
        try:
            # logger.debug(f"send: {data}")
            await self.__ws.send_str(json.dumps(data))
        except ConnectionResetError as e:
            logger.error(e)
            self.__scheduler.shutdown(wait=False)
            await stop_get_process_list()
            await self.__ws.close()
            logger.info('Stop WebSocket...')

    @logger.catch
    def get_base_data_save_path(self):
        """获取基本数据保存路径"""
        return self.__data_path
