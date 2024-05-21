from utils.logger import logger


async def authenticate(session, auth_path, auth_data):
    """
    客户端认证
    :param session: 会话对象
    :param auth_path: 认证地址
    :param auth_data: 认证数据
    """
    async with session.post(auth_path, json=auth_data) as resp:
        try:
            data = await resp.json()
            if data["status"] == 1:
                logger.info(f'认证成功')
                # server_config = data.get('data').get('config')
                return session
            else:
                logger.error(f"认证失败: {data['msg']}({data['status']})")
                exit(1)
        except Exception as e:
            print(e)
            logger.error(f"服务端返回了无效消息：\n{await resp.text()}(http code:{resp.status})")
            exit(1)