import hashlib

from utils.logger import logger
from utils.config import config

client_config = config().get_config

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
                data = data.get('data')
                server_token = data.get("server_token")
                if not server_token:
                    logger.error("认证失败，请检查服务端版本是否过低")
                    return False
                hash = server_token.get("hash")
                salt = server_token.get("salt")
                if not hash or not salt:
                    logger.error("认证失败，缺少必要参数")
                    return False
                if not __verify_password(hash, client_config().get('server').get('server_token'), salt):
                    logger.error("认证失败，服务端返回的认证信息不正确")
                logger.success(f'认证成功，欢迎连接：{data.get("server_name")}')
                return session
            else:
                logger.error(f"认证失败: {data['msg']}({data['status']})")
                return False
        except Exception as e:
            logger.error(f"服务端返回了无效消息：{await resp.text()}(http code:{resp.status})")
            return False


def __verify_password(hashed_password, password, salt):
    """
    验证密码
    """
    return hashed_password == str(hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ))