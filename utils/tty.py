import asyncio
import os
import sys
import uuid
import locale
from time import sleep

import utils.websocket as WebSocket
from threading import Thread

if sys.platform == 'win32':
    from winpty import PTY as WinPty
    Terminal = None
else:
    from utils.terminal import Terminal
from utils.logger import logger


class tty_service:
    __terminal: Terminal
    __session: dict[str: any] = {}
    __thread: dict[str: Thread] = {}

    def create_session(self, host=None, port=None, username=None, password=None):
        logger.debug("初始化终端")
        """创建终端会话"""
        child = None
        login_status = False
        if sys.platform != 'win32':
            self.__terminal = Terminal()
            child = self.__terminal.start(host, port, username, password)
            logger.debug('unix mode')
            if child is False:
                logger.warning("终端登录失败")
            else:
                login_status = True
        else:
            logger.debug("win32 mode")
            win32_terminal = WinPty(cols=80, rows=25)
            # appname = b'C:\\windows\\system32\\cmd.exe'
            appname = b'C:\\windows\\system32\\WindowsPowerShell\\v1.0\\powershell.exe'
            win32_terminal.spawn(appname.decode('utf-8'))
            child = win32_terminal
            login_status = True
        session_uuid = str(uuid.uuid1())
        if login_status:
            self.__session[session_uuid] = child
            logger.debug(f'create session uuid: {session_uuid}')
        else:
            del child
        return session_uuid, login_status

    def __del__(self):
        self.close()

    def get_session_list(self):
        """获取会话列表"""
        return self.__session.keys()

    def get_session(self, session_id):
        """获取终端会话"""
        if session_id in self.__session:
            return self.__session[session_id]
        else:
            logger.warning(f"[{session_id}]终端会话不存在")

    @logger.catch
    def resize(self, session_id, cols, rows):
        if session_id in self.__session:
            if sys.platform != 'win32':
                self.__session[session_id].resize_pty(cols, rows)
            else:
                self.__session[session_id].set_size(cols, rows)
        else:
            logger.warning(f"[{session_id}]终端会话不存在")

    @logger.catch
    def send_command(self, session_id, command):
        if session_id in self.__session:
            if sys.platform != 'win32':
                self.__session[session_id].send(command)
            else:
                self.__session[session_id].write(command)
        else:
            logger.warning(f"[{session_id}]终端会话不存在")

    @logger.catch
    def terminal_output(self, session_id, ws: WebSocket):
        async def __send(ws, data):
            await ws.websocket_send_json({'action': 'terminal:output', 'data': {'uuid': session_id, "output": data}})

        if session_id in self.__session:
            self.__thread[session_id] = Thread(
                target=self.__get_terminal_output,
                                               args=(session_id, lambda data: asyncio.run(__send(ws, data))))
            self.__thread[session_id].start()
        else:
            raise RuntimeError("终端会话不存在")

    @logger.catch
    def __get_terminal_output(self, session_id, callback):
        base_path = os.path.join(os.getcwd(), "data", "terminal_record")
        if not os.path.exists(base_path):
            os.mkdir(base_path)
        fd = open(str(os.path.join(os.getcwd(), os.path.join(base_path, session_id))), 'w+')
        while self.__session.get(session_id) is not None:
            output = ""
            if sys.platform != 'win32':
                if self.__session[session_id].recv_ready():
                    try:
                        output = self.__session[session_id].recv(1024).decode('utf-8')
                    except Exception as e:
                        logger.error(f"[Session: {session_id}] Get terminal output error! {e}")
            else:
                output = self.__session[session_id].read()
            if output != "":
                fd.write(output)
                callback(output)
            else:
                sleep(0.02)
        fd.close()
        logger.debug(f'session {session_id} get output stop')

    @logger.catch
    def close_session(self, session_id):
        logger.debug("关闭终端会话.....")
        """关闭终端会话"""
        if session_id in self.__session:
            del self.__session[session_id]
        else:
            logger.warning(f"[{session_id}]终端会话不存在")
    @logger.catch
    def close(self):
        temp = list(self.__session.keys())
        for session_id in temp:
            self.close_session(session_id)
