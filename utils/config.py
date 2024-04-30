import os.path

from utils.logger import logger

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


class config:
    __config = None

    def __init__(self):
        try:
            self.__load()
        except RuntimeError:
            logger.error('配置文件加载失败，应用启动失败')
            raise RuntimeError("配置文件加载失败，客户端启动失败")

    def __load(self):
        if not os.path.exists("config.toml"):
            self.__init_config()
        try:
            with open("config.toml", "rb") as f:
                self.__config = tomllib.load(f)
                logger.info("配置文件加载完成")
        except Exception as err:
            logger.error(err)
            raise RuntimeError("配置文件加载失败")

    def __init_config(self):
        file_data = """[server]
# 服务器地址
server_host = "127.0.0.1"
# 服务器端口号
server_port = 8080
# 服务器WebSocks路径(非特殊需要请勿修改!!! 默认值: /websocks/node)
server_path = "/websocks/node"
# 服务器Token
server_token = "xxxxxxxx"
# 启用SSL
enable_SSL = false
# 客户端名称
client_name = "client"
# 客户端Token(需与客户端名称对应)
client_token = "xxxxxxxx"
# 自动重连到服务器
re_connect = true

[safe]
# 允许服务器执行命令
execute_command = true
# 允许服务器访问文件
access_file = true
# 允许服务器连接终端
connect_terminal = true"""
        with open("config.toml", "w",encoding='utf-8') as f:
            f.write(file_data)
        logger.info("配置文件已初始化，请填写完成后重启本程序")
        exit(0)

    def reload(self):
        logger.debug("重新加载配置文件......")
        self.__load()

    def get_config(self):
        return self.__config
