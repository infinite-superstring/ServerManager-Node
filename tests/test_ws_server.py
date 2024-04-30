from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from aiohttp.web_ws import WebSocketResponse


async def http_handle(request: Request) -> Response:
    """
    HTTP 请求处理器
    """
    # web.get("/{name}", ...) 中的 name
    name = request.match_info.get("name")

    # 请求 Body, 也可以通过 await request.content.read(n) 逐块读取
    body = await request.text()

    resp_text = f"Your Request Info:\n" \
                f"name: {name}\n" \
                f"IP: {request.remote}\n" \
                f"Method: {request.method}\n" \
                f"Version: {request.version}\n" \
                f"Url: {request.url}\n" \
                f"Path: {request.path}\n" \
                f"Headers: {request.headers}\n" \
                f"Body: {body}"

    # 返回一个 响应对象
    return web.Response(status=200,
                        text=resp_text,
                        content_type="text/plain")


async def ws_handle(request: Request) -> WebSocketResponse:
    """
    WebSocket 请求处理器
    """
    # 创建一个 WebSocket 响应, 自动响应 CLOSE, 收到 PING 后自动回复 PONG
    ws = web.WebSocketResponse(autoclose=True, autoping=True)
    # 预处理请求
    await ws.prepare(request)

    # 循环处理消息, 直到 WebSocket 退出
    # ws.__anext__() 方法中调用了 await ws.receive() 接收消息并返回
    async for msg in ws:
        # msg: <class 'aiohttp.http_websocket.WSMessage'>
        if msg.type == web.WSMsgType.TEXT:
            print(msg.data)
            await ws.send_str(msg.data)
        elif msg.type == web.WSMsgType.BINARY:
            await ws.send_bytes(msg.data)
        elif msg.type == web.WSMsgType.CLOSE:
            break

    print("websocket connection closed.")
    return ws


# 创建一个 Web 应用
app = web.Application()

# 添加路由路径对应的处理器, 按列表顺序依次匹配
app.add_routes([web.get("/", http_handle),          # curl http://localhost:8080/
                web.post("/node/auth", http_handle),         # curl -d "aa=bb" http://localhost:8080/
                web.get("/websocks/node", ws_handle),        # ws://localhost:8080/echo
                web.get("/{name}", http_handle)])   # curl http://localhost:8080/hello

# 运行一个 Web 应用,
# 这里不需要在异步方法中运行, 内部会在 asyncio 异步事件循环中处理
web.run_app(app, host=None, port=8080)
