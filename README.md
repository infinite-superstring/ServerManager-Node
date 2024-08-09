# 节点客户端

## 配置项目
```shell
    # 新建虚拟环境
    python -m venv venv
    # 进入虚拟环境
    .\venv\Scripts\activate  # Windows
    source venv/bin/activate  # Linux
    # 安装依赖
    pip3 install -r requirements.txt
    
    python main.py
```


## 编译到可执行文件
**X86**
```shell
docker build -t  .
docker run --rm -v $(pwd)/output:/output my_python_app
```