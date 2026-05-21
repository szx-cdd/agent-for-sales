# 销售成单推演 Agent（客户管理版）

基于 Kimi AI 的销售助手，包含客户管理功能。

## 功能特点

- 客户画像分析（性格类型、需求匹配度、决策链）
- 跟进节奏规划（最佳跟进频率、关键时间点）
- 异议攻防策略（常见抗拒点应对话术）
- 沉默客户激活
- 客户管理系统（增删改查、聊天记录、分析历史）
- 支持文件上传（图片 OCR、PDF、Word、Excel）

## 快速启动

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

复制 `.env.example` 为 `.env`，填入你的 Moonshot API Key：

```
KIMI_API_KEY=your_api_key_here
```

### 3. 启动服务

Windows:
```bash
start.bat
```

或手动启动:
```bash
python main.py
```

## 访问地址

- 首页（销售推演）: http://localhost:8000
- 客户管理: http://localhost:8000/customers

## 项目结构

```
sales-agent-new/
├── main.py              # 主程序
├── database.py          # 数据库模块（SQLite）
├── document_processor.py # 文件处理模块
├── prompts.py           # AI 提示词
├── config.py            # 配置模块
├── templates/           # HTML 模板
│   ├── index.html       # 销售推演页面
│   ├── customers.html   # 客户列表页面
│   └── customer_detail.html # 客户详情页面
├── start.bat            # Windows 启动脚本
└── requirements.txt     # Python 依赖
```

## 部署

支持 Render、腾讯云、Docker 等多种部署方式，详见部署脚本。
