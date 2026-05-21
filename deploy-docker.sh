#!/bin/bash
# Docker 一键部署脚本（适用于腾讯云轻量服务器 Docker CE 镜像）

set -e

echo "===================================="
echo "销售 Agent Docker 部署脚本"
echo "===================================="

# 颜色输出
red() { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }

# 检查 Docker
if ! command -v docker &> /dev/null; then
    red "Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    yellow "安装 docker-compose..."
    apt-get update
    apt-get install -y docker-compose
fi

# 进入项目目录
cd /opt/sales-agent

# 构建并启动
yellow "[1/3] 构建 Docker 镜像..."
docker-compose build

yellow "[2/3] 启动服务..."
docker-compose up -d

yellow "[3/3] 检查服务状态..."
sleep 3
docker-compose ps

# 获取公网 IP
IP=$(curl -s ip.sb)

green "===================================="
green "部署完成！"
green "===================================="
green "访问地址：http://${IP}"
green ""
green "常用命令："
green "  查看日志：docker-compose logs -f"
green "  重启服务：docker-compose restart"
green "  停止服务：docker-compose down"
green "  更新代码后重建：docker-compose up -d --build"
green "===================================="
