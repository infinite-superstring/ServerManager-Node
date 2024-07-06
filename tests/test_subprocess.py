import subprocess

# 定义要执行的多行 shell 脚本
# script = """
# echo "Starting script..."
# ls -l
# echo "Listing completed."
# """

script = """
echo xxxx
echo xxxx
echo xxxx
echo xxxx
echo xxxx
pwd
python -version"""

# 执行多行 shell 脚本，设置 shell=True 并使用 bash 解释器执行
process = subprocess.Popen(["bash", "-c", script], cwd="/", stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# 实时读取输出流
while process.poll() is None:
    line = process.stdout.readline()
    line = line.strip()
    if line:
        print('Subprogram output: [{}]'.format(line))
if process.returncode == 0:
    print('Subprogram success')
else:
    print(f'Subprogram failed, code: {process.returncode}')

# 等待命令执行完成
process.communicate()
