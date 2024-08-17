import asyncio
import locale
import os
import subprocess
import sys
import tempfile
import time
from threading import Thread
from queue import Queue

from apscheduler.schedulers.background import BackgroundScheduler
from utils.logger import logger
import utils.websocket as websocket


class executeUtils:
    __websocket: websocket
    __websocket_message_queue: Queue
    __handle_websocket_thread: Thread | None = None
    __scheduler: BackgroundScheduler
    __process_list: dict[str: subprocess.Popen] = {}
    __get_process_thread: Thread | None = None
    __data_path: str
    __record_path: str
    __record_fd: dict[str:any] = {}
    __temp_filename: dict[str:str] = {}

    def __init__(self, ws):
        self.__websocket = ws
        self.__scheduler = BackgroundScheduler()
        self.__websocket_message_queue = Queue()
        # 初始化执行数据保存路径
        self.__record_path = os.path.join(self.__websocket.get_base_data_save_path(), "shell_execute")
        if not os.path.exists(self.__record_path):
            os.mkdir(self.__record_path)

    def executeShellCommand(self, execute_uuid, execute_path, shell_command):
        """
        执行Shell命令
        :param execute_uuid: 执行器uuid
        :param execute_path: 执行路径
        :param shell_command: 命令
        :return:
        """

        if sys.platform != 'win32':
            run = self.__run_shell
        else:
            run = self.__run_bat

        run(shell_command, execute_uuid, execute_path)

    @logger.catch
    def __run_shell(self, script, uuid, cwd: str = None):
        """
        运行Shell脚本
        """
        if not cwd:
            cwd = os.path.join(os.getcwd(), "shell_run")
        if not os.path.exists(cwd):
            os.mkdir(cwd)
        # 初始化任务保存路径
        save_path = os.path.join(self.__record_path, uuid)
        if not os.path.exists(save_path):
            os.mkdir(save_path)

        logger.debug(f"run shell script: {uuid} cwd: {cwd}")

        self.__send_websocket_action('execute:start', {
            'uuid': uuid,
            'timestamp': time.time()
        })

        # 执行多行 shell 脚本，设置 shell=True 并使用 bash 解释器执行
        self.__process_list[uuid] = subprocess.Popen(
            script,
            shell=True,
            cwd=cwd,
            executable='/bin/bash',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        self.__record_fd[uuid] = open(os.path.join(save_path, uuid), "w+", encoding='utf-8')
        record_info = (
            f"[INFO]\n"
            f"uuid: {uuid}\n"
            f"start time: {time.time()}\n"
            f"[INFO]\n"
            f"[SHELL]\n"
            f"{script}\n"
            f"[SHELL]\n"
            f"[OUTPUT]\n"
        )
        self.__record_fd[uuid].write(record_info)
        # 如果线程不存在则初始化线程
        if self.__get_process_thread is None:
            self.__get_process_thread = Thread(
                target=self.__get_process_output,
                args=()
            )
            self.__get_process_thread.start()

    @logger.catch
    def __run_bat(self, script, uuid, cwd: str = None):
        """运行批处理"""
        if not cwd:
            cwd = os.path.join(os.getcwd(), "bat_run")
        if not os.path.exists(cwd):
            os.mkdir(cwd)
        # 初始化任务保存路径
        save_path = os.path.join(self.__record_path, uuid)
        if not os.path.exists(save_path):
            os.mkdir(save_path)

        logger.debug(f"run bat: {uuid} cwd: {cwd}")

        self.__send_websocket_action('execute:start', {
            'uuid': uuid,
            'timestamp': time.time()
        })

        # 创建临时批处理文件
        with tempfile.NamedTemporaryFile(delete=False, suffix='.bat') as temp_file:
            temp_file.write(script.encode(locale.getpreferredencoding()))
            temp_filename = temp_file.name

        # 执行批处理文件并捕获标准输出和标准错误输出
        self.__process_list[uuid] = subprocess.Popen(
            temp_filename,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self.__temp_filename[uuid] = temp_filename
        self.__record_fd[uuid] = open(os.path.join(save_path, uuid), "w+", encoding='utf-8')
        record_info = (
            f"[INFO]\n"
            f"uuid: {uuid}\n"
            f"start time: {time.time()}\n"
            f"[INFO]\n\n"
            f"[BAT]\n"
            f"{script}\n"
            f"[BAT]\n\n"
            f"[OUTPUT]\n"
        )
        self.__record_fd[uuid].write(record_info)
        # 如果线程不存在则初始化线程
        if self.__get_process_thread is None:
            self.__get_process_thread = Thread(
                target=self.__get_process_output,
                args=()
            )
            self.__get_process_thread.start()

    @logger.catch
    def __get_process_output(self):
        """获取所有进程输出"""
        logger.debug("获取进程输出开始")
        while len(self.__process_list) > 0:
            close_list = []
            for i in self.__process_list:
                process = self.__process_list[i]
                line = process.stdout.readline()
                line = line.strip().decode(locale.getpreferredencoding(), errors="ignore")
                if line:
                    logger.debug(f'[uuid: {i}]Subprogram output: {line}')
                    self.__record_fd[i].write(f"{line}\n")
                    self.__send_websocket_action("execute:output", {
                        'uuid': i,
                        'line': line,
                        'timestamp': time.time()
                    })
                if process.poll() is not None and not line:
                    stdout, stderr = process.communicate()
                    if stderr:
                        logger.error(f"执行错误:{stderr.decode()}")
                    logger.debug(f"[uuid: {i}]进程结束(code:{process.poll()})")
                    self.__send_websocket_action("execute:stop", {
                        'uuid': i,
                        'code': process.returncode,
                        'error': stderr.decode(),
                        'timestamp': time.time()
                    })
                    end_info = (
                        f"[OUTPUT]\n\n"
                        f"[END]\n"
                        f"end time: {time.time()}\n"
                        f"return: {process.returncode}\n"
                    )
                    end_info += f"error: {stderr.decode()}\n" if stderr else ""
                    end_info += f"[END]"

                    if sys.platform == 'win32':
                        temp_filename = self.__temp_filename[i]
                        # 删除临时批处理文件
                        if os.path.exists(temp_filename):
                            os.remove(temp_filename)

                    self.__record_fd[i].write(end_info)
                    close_list.append(i)
            for i in close_list:
                logger.debug(f"delete process: {i}")
                del self.__process_list[i]
                self.__record_fd[i].close()
        logger.debug("获取进程输出结束")
        self.__get_process_thread = None

    @logger.catch
    def __send_websocket_action(self, action, payload: dict = None):
        if payload is None:
            payload = {}

        self.__websocket_message_queue.put({'action': action, 'data': payload})
        if self.__handle_websocket_thread is None:
            self.__get_process_thread = Thread(
                target=self.__handle_websocket_queue,
                args=()
            )
            self.__get_process_thread.start()

    def __handle_websocket_queue(self):
        while True:
            task = self.__websocket_message_queue.get()
            if not task:
                break
            try:
                asyncio.run(self.__websocket.websocket_send_json(task))
            except Exception as err:
                logger.error(f"Send WebSocket Message Error: {err}")
        self.__handle_websocket_queue = None
