import threading
import paramiko
import time

# 服务器信息
hostname = '127.0.0.1'
port = 22  # 默认SSH端口
username = 'fsj'
password = '123456'

# 创建一个SSH客户端对象
client = paramiko.SSHClient()

# 自动添加主机密钥
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

stop_event = threading.Event()

def send():
    try:
        while not stop_event.is_set():
            # 获取用户输入的命令
            command = input()

            if command.lower() == 'exit':
                stop_event.set()
                break

            # 发送命令
            channel.send(command + '\n')
    except Exception as e:
        print(f"Error in send: {e}")
    finally:
        # 关闭连接
        client.close()

def receive():
    try:
        while not stop_event.is_set():
            if channel.recv_ready():
                output = channel.recv(1024).decode('utf-8')
                print(output, end="")
    except Exception as e:
        print(f"Error in receive: {e}")

if __name__ == '__main__':
    try:
        # 连接到服务器
        client.connect(hostname, port, username, password)

        # 打开一个伪终端
        channel = client.invoke_shell()
        output = channel.recv(1024).decode('utf-8')
        print(output)

        # 启动接收线程
        receive_thread = threading.Thread(target=receive)
        receive_thread.start()

        # 启动发送函数
        send()

        # 等待接收线程完成
        receive_thread.join()
    except Exception as e:
        print(f"Error in main: {e}")
    finally:
        # 确保在程序结束时关闭连接
        client.close()
