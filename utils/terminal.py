import paramiko


class Terminal():
    def __init__(self):
        self.channel = None
        self.client= paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def start(self, hostname, port, username, password):
        try:
            # 连接到服务器
            self.client.connect(hostname, port, username, password)
            # 打开一个伪终端
            self.channel = self.client.invoke_shell()
            return self.channel
        except:
            return False


    def terminal_close(self):
        self.client.close()
