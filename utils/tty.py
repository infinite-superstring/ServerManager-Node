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
from utils.logger import logger
from utils.terminal import Terminal


class tty_service:
    __terminal: Terminal
    __session: dict[str: any] = {}
    __thread: dict[str: Thread] = {}

    def create_session(self, host=None, port=None, username=None, password=None):
        print("初始化终端")
        """创建终端会话"""
        if sys.platform != 'win32':
            self.__terminal = Terminal()
            child = self.__terminal.start(host, port, username, password)
            logger.debug('unix mode')
        else:
            logger.debug("win32 mode")
            win32_terminal = WinPty(cols=80, rows=25)
            appname = b'C:\\windows\\system32\\cmd.exe'
            win32_terminal.spawn(appname.decode('utf-8'))
            child = win32_terminal
            logger.debug(child)
        session_uuid = str(uuid.uuid1())
        logger.debug(f'create session uuid: {session_uuid}')
        self.__session[session_uuid] = child
        return session_uuid

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

    def send_command(self, session_id, command):
        if session_id in self.__session:
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
        index = 0
        fd = open(str(os.path.join(os.getcwd(), f'terminal_record/{session_id}.txt')), 'w+')
        while self.__session.get(session_id) is not None:
            output = ""
            if sys.platform != 'win32':
                if self.__session[session_id].recv_ready():
                    output = self.__session[session_id].recv(1024).decode('utf-8')

            else:
                output = self.__session[session_id].read()

            if output == "":
                index += 1
            else:
                index = 0
            if index > 5:
                sleep(0.02)
            else:
                # print(output, end='')
                fd.write(output)
                callback(output)
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
