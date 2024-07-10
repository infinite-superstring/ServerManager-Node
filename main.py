import asyncio
import os.path

import aiohttp

from utils.config import config
from utils.websocket import WebSocket
from utils.model import database, Task
from utils.logger import logger

# config = config().get_config
ws: WebSocket

async def main():

    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
        global ws
        ws = WebSocket(session)
        await ws.websocket_connect()



if __name__ == '__main__':
    logger.info("""
 _____        __ _       _ _          _____                           _        _             
|_   _|      / _(_)     (_) |        / ____|                         | |      (_)            
  | |  _ __ | |_ _ _ __  _| |_ ___  | (___  _   _ _ __   ___ _ __ ___| |_ _ __ _ _ __   __ _ 
  | | | '_ \|  _| | '_ \| | __/ _ \  \___ \| | | | '_ \ / _ \ '__/ __| __| '__| | '_ \ / _` |
 _| |_| | | | | | | | | | | ||  __/  ____) | |_| | |_) |  __/ |  \__ \ |_| |  | | | | | (_| |
|_____|_| |_|_| |_|_| |_|_|\__\___| |_____/ \__,_| .__/ \___|_|  |___/\__|_|  |_|_| |_|\__, |
                                                 | |                                    __/ |
                                                 |_|                                   |___/ 
前端：https://github.com/infinite-superstring/ServerManager-UI
后端：https://github.com/infinite-superstring/ServerManager-Panel
节点：https://github.com/infinite-superstring/ServerManager-Node
        """)
    if not os.path.exists('data'):
        os.mkdir('data')
    database.create_tables([Task])
    asyncio.run(main())
