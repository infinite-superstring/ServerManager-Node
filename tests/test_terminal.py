import os
import pty
import subprocess
import select


def interact_with_subprocess():
    # 创建伪终端对
    master_fd, slave_fd = pty.openpty()

    # 启动子进程并将其标准输入/输出/错误重定向到伪终端的从端
    process = subprocess.Popen(
        ['/bin/bash'],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        text=True
    )

    # 关闭从端文件描述符
    os.close(slave_fd)

    try:
        while True:
            # 使用 select 监听标准输入和伪终端主端
            rlist, _, _ = select.select([master_fd, sys.stdin], [], [])

            for fd in rlist:
                if fd == master_fd:
                    # 从伪终端读取子进程的输出并打印到标准输出
                    data = os.read(fd, 1024).decode()
                    if data:
                        print(data, end='', flush=True)
                    else:
                        return

                elif fd == sys.stdin:
                    # 从标准输入读取用户输入并写入伪终端
                    user_input = sys.stdin.read(1)
                    if user_input:
                        os.write(master_fd, user_input.encode())
                    else:
                        return
    except KeyboardInterrupt:
        pass
    finally:
        # 关闭伪终端主端文件描述符
        os.close(master_fd)
        process.terminate()
        process.wait()


if __name__ == "__main__":
    import sys

    interact_with_subprocess()
