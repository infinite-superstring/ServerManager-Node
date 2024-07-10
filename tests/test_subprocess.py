# import subprocess
#
# # 定义要执行的多行 shell 脚本
# # script = """
# # echo "Starting script..."
# # ls -l
# # echo "Listing completed."
# # """
#
# script = """
# echo xxxx
# echo xxxx
# echo xxxx
# echo xxxx
# echo xxxx
# pwd
# python -version"""
#
# # 执行多行 shell 脚本，设置 shell=True 并使用 bash 解释器执行
# process = subprocess.Popen(["bash", "-c", script], cwd="/", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#
# # 实时读取输出流
# while process.poll() is None:
#     line = process.stdout.readline()
#     line = line.strip()
#     if line:
#         print('Subprogram output: [{}]'.format(line))
# if process.returncode == 0:
#     print('Subprogram success')
# else:
#     print(f'Subprogram failed, code: {process.returncode}')
#
# # 等待命令执行完成
# process.communicate()


import subprocess
import sys

command = """
for (( i=1; i<=1000; i++ )); do
    echo $i
done
"""

# 执行 shell 命令并捕获标准输出和标准错误输出
process = subprocess.Popen(command, shell=True, executable='/bin/bash', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = process.communicate()

# 检查返回码
return_code = process.returncode
if return_code == 0:
    print("命令执行成功")
    print(stdout.decode())
else:
    sys.stderr.write(f"命令执行失败，返回码为 {return_code}\n")
    sys.stderr.write(stderr.decode())  # 输出标准错误输出内容
