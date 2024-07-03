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
    __is_login = False

    def create_session(self, host=None, port=None, username=None, password=None):
        print("初始化终端")
        """创建终端会话"""
        child = None
        self.__is_login=False
        if sys.platform != 'win32':
            try:
                self.__terminal = Terminal()
                child = self.__terminal.start(host, port, username, password)
                logger.debug('unix mode')
                if child:
                    self.__is_login = True
            except Exception as e:
                self.__is_login = False
        else:
            try:
                logger.debug("win32 mode")
                win32_terminal = WinPty(cols=80, rows=25)
                # appname = b'C:\\windows\\system32\\cmd.exe'
                appname = b'C:\\windows\\system32\\WindowsPowerShell\\v1.0\\powershell.exe'
                win32_terminal.spawn(appname.decode('utf-8'))
                child = win32_terminal
                self.__is_login = True
                logger.debug(child)
            except Exception as e:
                self.__is_login = False
        session_uuid = str(uuid.uuid1())
        logger.debug(f'create session uuid: {session_uuid}')
        self.__session[session_uuid] = child
        print('登录？', self.__is_login)
        return session_uuid, self.__is_login

    def __del__(self):
        self.close()
        if self.__terminal is not None:
            self.__terminal.client.close()

    def get_session_list(self):
        """获取会话列表"""
        return self.__session.keys()

    def get_session(self, session_id):
        """获取终端会话"""
        if session_id in self.__session:
            return self.__session[session_id]
        else:
            raise RuntimeError("终端会话不存在")

    def resize(self, session_id, cols, rows):
        if session_id in self.__session:
            if self.__is_login:
                if sys.platform != 'win32':
                    self.__session[session_id].resize_pty(cols, rows)
                else:
                    self.__session[session_id].set_size(cols, rows)
        else:
            raise RuntimeError("终端会话不存在")

    def send_command(self, session_id, command, __is_login=None):
        if session_id in self.__session:
            if __is_login:
                if sys.platform != 'win32':
                    self.__session[session_id].send(command)
                else:
                    self.__session[session_id].write(command)
        else:
            raise RuntimeError("终端会话不存在")

    def terminal_output(self, session_id, ws: WebSocket):
        async def __send(ws, data):
            await ws.websocket_send_json({'action': 'terminal:output', 'data': {'uuid': session_id, "output": data}})

        if session_id in self.__session:
            self.__thread[session_id] = Thread(target=self.__get_terminal_output,
                                               args=(session_id, lambda data: asyncio.run(__send(ws, data))))
            self.__thread[session_id].start()
        else:
            raise RuntimeError("终端会话不存在")

    def __get_terminal_output(self, session_id, callback):
        # index = 0
        if not os.path.exists("terminal_record"):
            os.mkdir("terminal_record")
        fd = open(str(os.path.join(os.getcwd(), f'terminal_record/{session_id}.txt')), 'w+')
        while self.__session.get(session_id) is not None:
            output = ""
            is_out_put = False
            if sys.platform != 'win32':
                try:
                    if self.__session[session_id].recv_ready():
                        output = self.__session[session_id].recv(1024).decode('utf-8')
                        is_out_put = True
                except:
                    is_out_put = False
            else:
                try:
                    output = self.__session[session_id].read()
                    is_out_put = True
                except:
                    is_out_put = False
            # if output == "":
            #     index += 1
            # else:
            #     index = 0
            # if index > 5:
            #     sleep(0.02)
            # else:
            #     fd.write(output)
            #     callback(output)
            # if output != "":
            if is_out_put:
                fd.write(output)
                callback(output)
            else:
                sleep(0.02)
        fd.close()
        logger.debug(f'session {session_id} get output stop')

    def close_session(self, session_id):
        print("关闭终端会话.....")
        """关闭终端会话"""
        if session_id in self.__session:
            del self.__session[session_id]
        else:
            logger.warning('"终端会话关闭"')

    def close(self):
        temp = list(self.__session.keys())
        print(temp)
        for session_id in temp:
            self.close_session(session_id)
