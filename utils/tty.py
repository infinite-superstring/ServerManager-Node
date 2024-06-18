import asyncio
import sys
import uuid
import locale
from copy import copy

import pexpect
import utils.websocket as WebSocket
from threading import Thread

from utils.logger import logger


class tty_service:
    __session: dict[str: any] = {}
    __thread: dict[str: Thread] = {}

    def create_session(self):
        print("初始化终端")
        """创建终端会话"""
        if sys.platform != 'win32':
            child = pexpect.spawn('dir')
        else:
            from pexpect import popen_spawn
            child = pexpect.popen_spawn.PopenSpawn('cmd')
        session_uuid = str(uuid.uuid1())
        logger.debug(f'create session uuid: {session_uuid}')
        self.__session[session_uuid] = child
        return session_uuid

    def get_session_list(self):
        """获取会话列表"""
        return self.__session.keys()

    def get_session(self, session_id):
        """获取终端会话"""
        if session_id in self.__session:
            return self.__session[session_id]
        else:
            raise RuntimeError("Terminal session does not exist")

    def send_command(self, session_id, command):
        if session_id in self.__session:
            if locale.getpreferredencoding() != 'utf-8':
                command = command.encode(locale.getpreferredencoding())
            self.__session[session_id].sendline(command)
        else:
            raise RuntimeError("Terminal session does not exist")

    def terminal_output(self, session_id, ws: WebSocket):
        async def __send(ws, data):
            await ws.websocket_send_json({'action': 'terminal_output', 'data': {'uuid': session_id, "output": data}})

        if session_id in self.__session:
            self.__thread[session_id] = Thread(target=self.__get_terminal_output, args=(session_id, lambda data: asyncio.run(__send(ws, data))))
            self.__thread[session_id].start()
        else:
            raise RuntimeError("Terminal session does not exist")

    def __get_terminal_output(self, session_id, callback):
        while self.__session.get(session_id) is not None:
            try:
                callback(self.__session[session_id].readline().decode(locale.getpreferredencoding(), errors='ignore'))
            except pexpect.TIMEOUT:
                pass
            except KeyboardInterrupt:
                return

    def close_session(self, session_id):
        print("关闭终端会话.....")
        """关闭终端会话"""
        if session_id in self.__session:
            if sys.platform != 'win32':
                self.__session[session_id].terminate(force=True)
                self.__session[session_id].close()
                self.__session.pop(session_id)
            else:
                del self.__session[session_id]
        else:
            logger.warning('"Terminal session does not exist"')

    def close(self):
        temp = list(self.__session.keys())
        print(temp)
        for session_id in temp:
            self.close_session(session_id)
