import asyncio
import hashlib
import os.path
import time
from queue import Queue
from threading import Thread

import re
from urllib.parse import unquote, urlparse

from aiohttp import ClientSession
from utils.logger import logger

import utils.websocket as websocket


class DownloadTaskConfig:
    """
    下载任务配置
    """
    task_id: str
    params: dict
    save_path: str
    check_hash: bool
    file_hash: str

    def __init__(self, task_id: str, params: dict, save_path: str, check_hash: bool, file_hash: str):
        self.task_id = task_id
        self.params = params
        self.save_path = save_path
        self.check_hash = check_hash
        self.file_hash = file_hash


class DownloadFileUtil:
    __websocket: websocket
    __websocket_message_queue: Queue
    __session: ClientSession
    __download_queue: Queue
    __max_download_thread: int = 0
    __download_threads: int = 0
    __handle_websocket_thread: Thread | None = None
    __handle_download_start_thread: Thread | None = None
    __url: str
    __loop: asyncio.AbstractEventLoop

    def __init__(self, ws: websocket, client_session: ClientSession, url: str, max_download_threads: int = 4):
        """
        :param ws: WebSocket instance
        :param client_session: Aiohttp client session
        :param url: URL
        """
        self.__websocket = ws
        self.__session = client_session
        logger.debug(self.__session)
        self.__url = url
        self.__websocket_message_queue = Queue()
        self.__download_queue = Queue()
        self.__max_download_thread = max_download_threads
        self.__loop = asyncio.get_event_loop()  # 获取当前事件循环

    def __get_file_name(self, response):
        # 提取文件名
        disposition = response.headers.get('Content-Disposition', '')
        logger.debug(disposition)
        filename_match = re.findall('filename=(.*)', disposition)
        logger.debug(filename_match)
        filename = filename_match[0]

        # 处理文件名的 URL 解码
        filename = unquote(filename)
        return filename

    async def download_file(self, task_id: str, params: dict, save_path: str, check_hash: bool = False,
                            file_hash: str = None):
        """
        下载文件
        :param task_id: 任务标识符
        :param params: GET请求参数
        :param save_path: 保存路径
        :param check_hash: 校验文件哈希
        :param file_hash: 目标文件哈希
        """
        self.__download_queue.put(DownloadTaskConfig(task_id, params, save_path, check_hash, file_hash))
        if self.__handle_download_start_thread is None:
            logger.debug("创建处理任务进程")
            self.__handle_download_start_thread = Thread(
                target=self.__handle_download_queue,
                args=()
            )
            self.__handle_download_start_thread.start()

    async def __download(self, download_task: DownloadTaskConfig):
        """
        下载任务实例
        :param download_task:
        :return:
        """
        logger.debug(download_task)
        if not os.path.exists(download_task.save_path):
            os.makedirs(download_task.save_path)
        try:
            async with self.__session.get(self.__url, params=download_task.params) as response:
                if response.status != 200:
                    self.__download_threads -= 1
                    return self.__send_websocket_action('file_download:failure', {
                        'task': download_task.task_id,
                        'error_type': "HTTP Status Code不正确",
                        'error_content': f"Status Code: {response.status}"
                    })
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    logger.error(f"下载文件返回错误数据类型：{response.json()}")
                    self.__download_threads -= 1
                    return self.__send_websocket_action('file_download:failure', {
                        'task': download_task.task_id,
                        'error_type': "返回数据无效/无权限",
                        'error_content': str(response.text())
                    })
                filename = self.__get_file_name(response)
                sha256 = hashlib.sha256()
                # 下载并保存文件
                logger.debug("下载开始")
                with open(os.path.join(download_task.save_path, filename), 'wb') as file:
                    while True:
                        chunk = await response.content.read(8192)
                        sha256.update(chunk)
                        if not chunk:
                            break
                        file.write(chunk)
                sha256 = sha256.hexdigest()
                # 校验哈希
                if download_task.check_hash and (
                        download_task.file_hash is not None or download_task.file_hash != sha256):
                    self.__download_threads -= 1
                    return self.__send_websocket_action('file_download:failure', {
                        'task': download_task.task_id,
                        'error_type': "文件哈希校验失败",
                        'error_content': f"{download_task.file_hash} != {sha256}"
                    })
        except Exception as e:
            logger.error(e)
            self.__download_threads -= 1
            return self.__send_websocket_action('file_download:failure', {
                'task': download_task.task_id,
                'error_type': "请求错误/未知错误",
                'error_content': str(e)
            })
        self.__download_threads -= 1
        logger.success(f"文件 {filename} 下载成功")
        return self.__send_websocket_action('file_download:success', {
            'task': download_task.task_id,
            'file_hash': sha256
        })

    @logger.catch
    def __send_websocket_action(self, action, payload: dict = None):
        """发送websocket action消息"""
        if payload is None:
            payload = {}

        self.__websocket_message_queue.put({'action': action, 'data': payload})
        if self.__handle_websocket_thread is None:
            self.__handle_websocket_thread = Thread(
                target=self.__handle_websocket_queue,
                args=()
            )
            self.__handle_websocket_thread.start()

    def __handle_websocket_queue(self):
        """
        处理消息发送队列
        :return:
        """
        while True:
            task = self.__websocket_message_queue.get()
            if not task:
                break
            try:
                asyncio.run_coroutine_threadsafe(
                    self.__websocket.websocket_send_json(task),
                    self.__loop
                )
            except Exception as err:
                logger.error(f"Send WebSocket Message Error: {err}")
        self.__handle_websocket_thread = None

    def __handle_download_queue(self):
        """
        处理下载队列
        :return:
        """
        while True:
            task = self.__download_queue.get()
            if not task:
                break
            elif self.__download_threads >= self.__max_download_thread:
                time.sleep(0.3)
            try:
                asyncio.run_coroutine_threadsafe(
                    self.__download(task),
                    self.__loop
                )
                self.__download_threads += 1
            except Exception as err:
                logger.error(f"Run Download Task Error: {err}")
                self.__send_websocket_action('file_download:failure', {
                    'task': task.task_id,
                    'error_type': "请求错误/未知错误（启动任务时）",
                    'error_content': str(err)
                })
        self.__handle_download_start_thread = None
