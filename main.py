import asyncio

import aiohttp

from utils.config import config
from utils.websocket import WebSocket

# config = config().get_config
ws: WebSocket

async def main():

    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True)) as session:
        global ws
        ws = WebSocket(session)
        await ws.websocket_connect()



if __name__ == '__main__':
    asyncio.run(main())
