# QMT HTTP Server

基于 FastAPI 的 QMT 行情交易 HTTP 服务，将 QMT 终端功能封装为 REST API，支持跨平台调用。

---

## 目录

- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [配置说明](#配置说明)
- [运行方式](#运行方式)
- [接口文档](#接口文档)
- [常见问题](#常见问题)

---

## 环境要求

| 项目 | 要求 | 说明 |
|------|------|------|
| 操作系统 | **Windows** | QMT 终端仅支持 Windows |
| Python | **3.10 / 3.11** | xtquant .pyd 限制，不支持 3.12+ |
| QMT 终端 | **已安装并运行** | 国金/迅投 QMT 量化交易终端 |
| 网络 | **本地/局域网** | 默认监听 0.0.0.0:8080 |

---

## 快速启动

### 1. 安装依赖

```bash
cd qmt_server
pip install -r requirements.txt
```

### 2. 配置环境变量

```powershell
# 必需：xtquant 路径（根据实际安装位置调整）
$env:QMT_XTQUANT_PATH="D:/software/54QMT/国金证券QMT交易端/bin.x64/Lib/site-packages"

# 可选：交易功能配置（如不使用交易接口，可不配置）
$env:QMT_USERDATA_PATH="D:/software/54QMT/国金QMT交易端模拟/userdata_mini"
$env:QMT_ACCOUNT_ID="90007183"

# 可选：服务端口号（默认 8080）
$env:QMT_SERVER_PORT="8080"
```

### 3. 启动服务

#### 方式 A：在项目根目录启动（推荐）

```bash
# 进入项目根目录
cd D:\work\code\TradingAgents-CN

# 方式 1：使用 uvicorn（推荐）
python -m uvicorn qmt_server.main:app --host 0.0.0.0 --port 8080 --log-level info

# 方式 2：直接运行（调试用）
python -m qmt_server.main

# 方式 3：生产模式（多 worker）
python -m uvicorn qmt_server.main:app --host 0.0.0.0 --port 8080 --workers 2
```

#### 方式 B：在 qmt_server 目录内启动

```bash
# 进入 qmt_server 目录
cd D:\work\code\TradingAgents-CN\qmt_server

# 设置 PYTHONPATH 为父目录，然后启动
$env:PYTHONPATH="D:\work\code\TradingAgents-CN"
python -m uvicorn main:app --host 0.0.0.0 --port 8080 --log-level info

# Linux/Mac
export PYTHONPATH=/path/to/TradingAgents-CN
python -m uvicorn main:app --host 0.0.0.0 --port 8080
```

> **方式 B 注意**：必须设置 `PYTHONPATH` 环境变量指向项目根目录，否则会出现 `No module named 'qmt_server'` 错误！

### 4. 验证启动

```bash
# 健康检查
curl http://localhost:8080/api/v1/system/health

# 环境诊断
curl http://localhost:8080/api/v1/system/doctor
```

---

## 配置说明

### 环境变量

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `QMT_XTQUANT_PATH` | ✅ | - | xtquant 库路径，含 `xtquant` 文件夹 |
| `QMT_USERDATA_PATH` | ❌ | - | QMT userdata_mini 路径（交易功能必需）|
| `QMT_ACCOUNT_ID` | ❌ | - | QMT 账号 ID（交易功能必需）|
| `QMT_SERVER_PORT` | ❌ | `8080` | HTTP 服务端口号 |

### 查找 xtquant 路径

在 QMT 终端安装目录中查找：

```
QMT安装目录/
├── bin.x64/
│   └── Lib/
│       └── site-packages/
│           └── xtquant/          ← 这个就是
│               ├── __init__.py
│               ├── xtdata.py
│               └── xttrader.py
```

### 查找 userdata_mini 路径

模拟交易用户数据目录：

```
QMT安装目录/
├── 国金QMT交易端模拟/           ← Mini 模式
│   └── userdata_mini/          ← 使用这个
│       ├── account.dat
│       └── ...
├── 国金QMT交易端实盘/             ← 实盘模式（如需实盘使用）
│   └── userdata/
```

---

## 运行方式

### 开发模式（热重载）

```bash
python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload --log-level debug
```

### 后台运行（Windows）

```powershell
# 使用 PowerShell 后台运行
Start-Process python -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port 8080" -WindowStyle Hidden

# 或使用 nohup 等价物
python -m uvicorn main:app --host 0.0.0.0 --port 8080 > qmt_server.log 2>&1
```

### 开机自启（Windows 计划任务）

1. 创建启动脚本 `start_qmt_server.bat`：

```batch
@echo off
set QMT_XTQUANT_PATH=D:\software\54QMT\国金证券QMT交易端\bin.x64\Lib\site-packages
set QMT_USERDATA_PATH=D:\software\54QMT\国金QMT交易端模拟\userdata_mini
set QMT_ACCOUNT_ID=90007183
set QMT_SERVER_PORT=8080

cd /d D:\work\code\TradingAgents-CN\qmt_server
python -m uvicorn main:app --host 0.0.0.0 --port 8080 --log-level info >> qmt_server.log 2>&1
```

2. 创建计划任务：
   - 任务计划程序 → 创建任务
   - 触发器：用户登录时
   - 操作：启动程序 → 选择 `start_qmt_server.bat`

---

## 接口文档

启动后访问自动生成的文档：

| 文档类型 | 地址 |
|----------|------|
| Swagger UI | http://localhost:8080/docs |
| ReDoc | http://localhost:8080/redoc |
| OpenAPI JSON | http://localhost:8080/openapi.json |

### 主要接口

#### 系统接口 `/api/v1/system`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/doctor` | 环境诊断 |
| GET | `/status` | 服务器状态 |

#### 行情接口 `/api/v1/market`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/quote/{code}` | 单只行情 |
| GET | `/quote?codes=xxx,yyy` | 批量行情 |
| GET | `/kline/{code}?period=1d&count=100` | K线数据 |
| GET | `/tick/{code}` | 五档盘口 |
| GET | `/stock-list` | 股票列表 |
| GET | `/market-overview` | 大盘指数 |

#### 账户接口 `/api/v1/account`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/asset` | 账户资产 |
| GET | `/positions` | 持仓查询 |
| GET | `/orders` | 委托查询 |
| GET | `/trades` | 成交查询 |

#### 交易接口 `/api/v1/trade`

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/buy` | 买入下单 |
| POST | `/sell` | 卖出下单 |
| POST | `/cancel` | 撤单 |

**重要**：交易接口默认预演模式，需加 `confirm: true` 才真正下单！

---

## 常见问题

### 1. 启动报错 `ModuleNotFoundError: No module named 'xtquant'`

**解决**：环境变量 `QMT_XTQUANT_PATH` 设置错误，请指向含 `xtquant` 文件夹的目录。

```powershell
# 错误示例
$env:QMT_XTQUANT_PATH="D:/software/54QMT/国金证券QMT交易端/bin.x64/Lib/site-packages/xtquant"

# 正确示例
$env:QMT_XTQUANT_PATH="D:/software/54QMT/国金证券QMT交易端/bin.x64/Lib/site-packages"
```

### 2. 健康检查返回 `qmtConnected: false`

**解决**：QMT 终端未运行，请先启动 QMT 终端并登录。

### 3. 交易接口报错 "Trade service not ready"

**解决**：未配置交易账号，需设置 `QMT_USERDATA_PATH` 和 `QMT_ACCOUNT_ID`。

### 4. 端口冲突 `error while attempting to bind on address ('0.0.0.0', 8080)`

**解决**：端口被占用，更换端口：

```powershell
$env:QMT_SERVER_PORT="8081"
python -m uvicorn main:app --host 0.0.0.0 --port 8081
```

### 5. K线接口超时

**解决**：首次获取需下载历史数据，建议客户端设置 60 秒超时，或先预加载常用数据。

### 6. 股票列表接口慢

**解决**：首次调用 `sync=true` 需下载板块数据（约 30-60 秒），后续使用 `sync=false` 更快。

---

## 客户端配置

TradingAgents-CN 连接配置示例：

```python
# app/core/config.py 或环境变量
QMT_SERVER_URL = "http://192.168.1.100:8080"  # QMT Server 地址
QMT_SERVER_TIMEOUT = 30                       # 请求超时（秒）
QMT_SERVER_ENABLED = True                     # 启用 HTTP 客户端模式
```

---

## 项目结构

```
qmt_server/
├── main.py                 # FastAPI 入口
├── config.py               # 配置加载
├── requirements.txt        # 依赖
├── routers/                # 路由
│   ├── system.py          # 系统接口
│   ├── market.py          # 行情接口
│   ├── account.py         # 账户接口
│   └── trade.py           # 交易接口
├── services/               # 服务层
│   ├── xtquant_service.py # xtdata 封装
│   └── trade_service.py   # xttrader 封装
├── models/                 # 数据模型
│   └── schemas.py         # Pydantic 模型
└── middleware/             # 中间件
    └── rate_limit.py      # 限流
```

---

## 支持与反馈

- **GitHub Issues**: [TradingAgents-CN](https://github.com/chenjie222/TradingAgents-CN)
- **接口文档**: 启动后访问 http://localhost:8080/docs
