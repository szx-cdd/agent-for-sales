#!/bin/bash
# 腾讯云轻量服务器一键部署脚本
# 使用方法：
# 1. 购买服务器后，用 SSH 工具（如 Xshell、PuTTY）连接
# 2. 上传此脚本到服务器：scp deploy-tencent.sh root@你的服务器IP:/root/
# 3. 执行：chmod +x deploy-tencent.sh && ./deploy-tencent.sh

set -e

echo "===================================="
echo "销售 Agent 自动部署脚本"
echo "===================================="

# 颜色输出
red() { echo -e "\033[31m$1\033[0m"; }
green() { echo -e "\033[32m$1\033[0m"; }
yellow() { echo -e "\033[33m$1\033[0m"; }

# 更新系统
yellow "[1/7] 更新系统..."
apt-get update -y
apt-get upgrade -y

# 安装必要软件
yellow "[2/7] 安装 Python 和依赖..."
apt-get install -y python3 python3-pip python3-venv git nginx

# 克隆项目
cd /opt
if [ -d "sales-agent" ]; then
    yellow "项目已存在，正在更新..."
    cd sales-agent
    git pull
else
    yellow "[3/7] 下载项目代码..."
    # 如果用户用 GitHub，改成 git clone https://github.com/用户名/sales-agent.git
    # 这里先用本地文件方式，需要用户先上传代码压缩包
    echo "请先将项目代码上传到 /opt/sales-agent/ 目录"
    exit 1
fi

# 创建虚拟环境
yellow "[4/7] 创建 Python 虚拟环境..."
cd /opt/sales-agent
python3 -m venv venv
source venv/bin/activate

# 安装依赖
yellow "[5/7] 安装 Python 依赖..."
pip install --upgrade pip
pip install -r requirements.txt

# 创建环境变量文件
yellow "[6/7] 配置环境变量..."
cat > .env << 'EOF'
KIMI_API_KEY=sk-x5YNWu5BZeGyVGKiuQG90obxZlT1R2xMhSSa4A5d7bkdbuoO
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=moonshot-v1-8k-vision-preview
KIMI_TEXT_MODEL=moonshot-v1-32k
MAX_TOKENS=4096
TEMPERATURE=0.7
EOF

# 创建 systemd 服务
yellow "[7/7] 创建系统服务..."
cat > /etc/systemd/system/sales-agent.service << 'EOF'
[Unit]
Description=Sales Agent Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/sales-agent
Environment=PATH=/opt/sales-agent/venv/bin
ExecStart=/opt/sales-agent/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# 配置 Nginx
cat > /etc/nginx/sites-available/sales-agent << 'EOF'
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

ln -sf /etc/nginx/sites-available/sales-agent /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 启动服务
systemctl daemon-reload
systemctl enable sales-agent
systemctl start sales-agent
systemctl restart nginx

# 配置防火墙
ufw allow 80/tcp
ufw allow 22/tcp
ufw --force enable

green "===================================="
green "部署完成！"
green "===================================="
green "访问地址：http://$(curl -s ip.sb)"
green ""
green "常用命令："
green "  查看状态：systemctl status sales-agent"
green "  重启服务：systemctl restart sales-agent"
green "  查看日志：journalctl -u sales-agent -f"
green "===================================="
