# 检测系统发行版
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        echo "Unsupported OS"
        exit 1
    fi
}

# 安装 Docker 和 Docker Compose
install_docker() {
    case "$OS" in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y \
                apt-transport-https \
                ca-certificates \
                curl \
                gnupg \
                lsb-release
            curl -fsSL https://download.docker.com/linux/$OS/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            echo \
                "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/$OS \
                $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io
            ;;
        centos|fedora|rhel)
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io
            ;;
        *)
            echo "Unsupported OS"
            exit 1
            ;;
    esac

    sudo systemctl start docker
    sudo systemctl enable docker
}

ARCH=$(uname -m)

if [ "$ARCH" = "x86_64" ]; then
    detect_os
    install_docker
    docker build -f Dockerfile.x86 -t build_node_client:x86_64
    docker run --rm -v $(pwd)/output:/output build_node_client:x86_64
elif [ "$ARCH" = "loongarch64" ]; then
    yum install -y wget git
    # 安装 docker ce
    if [ ! -f 'installer/loongarch64/docker.service' ]; then
      tar -xf ./installer/loongarch64/docker-27.0.3.tgz
      mv docker/* /usr/local/bin/
      rm -rf docker
      cp ./installer/loongarch64/docker.service /etc/systemd/system/docker.service
      systemctl daemon-reload
      systemctl start docker
      systemctl enable docker
      # 清理
      rm -rf docker
    docker build -f Dockerfile.loongarch -t build_node_client:loongarch64
    docker run --rm -v $(pwd)/output:/output build_node_client:loongarch64
    fi
else
    echo "不支持的系统架构: ${ARCH}" && exit 1;
fi