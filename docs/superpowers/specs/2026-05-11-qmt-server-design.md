# QMT HTTP Server 设计文档

**版本**: 1.0
**日期**: 2026-05-11
**状态**: Draft

---

## 1. 项目概述

### 1.1 背景

TradingAgents-CN 当前集成 QMT 数据源通过本地 `xtquant` 库直接连接 QMT 终端，这要求 TradingAgents-CN 必须部署在 Windows 上且与 QMT 终端在同一机器。

为实现跨平台部署，将 QMT 连接逻辑抽取为独立的 HTTP Server：
- **Server 端**：部署在 Windows 上，直连 QMT 终端，暴露 HTTP API
- **Client 端**：TradingAgents-CN 通过 HTTP 调用获取数据，可部署在任意平台

### 1.2 架构

```
┌─────────────────────────────────────────────────────────┐
│  TradingAgents-CN (任意平台)                              │
│  ├── app/services/data_sources/qmt_adapter.py           │
│  │   └── HTTP Client → QMT Server                       │
│  └── 配置: QMT_SERVER_URL=http://windows-server:8080    │
└───────────────────────HTTP──────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  QMT Server (Windows)                                    │
│  ├── FastAPI 应用                                        │
│  ├── xtquant 本地连接 QMT 终端                           │
│  ├── qmt_server/                                         │
│  │   ├── main.py              (应用入口)                 │
│  │   ├── config.py            (配置管理)                 │
│  │   ├── routers/                                         │
│  │   │   ├── market.py        (行情接口)                 │
│  │   │   ├── account.py       (账户查询)                 │
│  │   │   ├── trade.py         (交易接口)                 │
│  │   │   └── system.py        (系统/诊断)                │
│  │   ├── services/                                        │
│  │   │   ├── xtquant_service.py (xtquant 封装)          │
│  │   │   └── trade_service.py  (交易封装)               │
│  │   └── models/                                          │
│  │       └── schemas.py       (Pydantic 模型)            │
│  └── scripts/config.json      (QMT 配置)                 │
└─────────────────────────────────────────────────────────┘
```

### 1.3 技术栈

- **Python**: 3.10 / 3.11（xtquant .pyd 限制）
- **Web 框架**: FastAPI
- **数据源**: xtquant (xtdata + xttrader)
- **运行平台**: Windows only（QMT 终端要求）
- **端口**: 8080（可配置）

---

## 2. 接口设计

### 2.1 基础 URL

```
http://{host}:{port}/api/v1/{module}/{action}
```

所有响应统一格式：

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": { ... },
  "message": "操作成功"
}
```

错误响应：

```json
{
  "success": false,
  "timestamp": "2026-05-11T15:30:00",
  "error": {
    "code": "QMT_NOT_CONNECTED",
    "message": "QMT 终端未运行或连接失败",
    "details": "..."
  }
}
```

---

## 3. 行情接口 (Market)

**Base URL**: `/api/v1/market`

### 3.1 实时行情快照 - 单只

**端点**: `GET /api/v1/market/quote/{code}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 6位股票代码或完整代码，如 `000001` 或 `000001.SZ` |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "code": "000001",
    "fullCode": "000001.SZ",
    "name": "平安银行",
    "open": 10.50,
    "high": 10.68,
    "low": 10.42,
    "close": 10.55,
    "preClose": 10.48,
    "change": 0.07,
    "changePct": 0.67,
    "volume": 125000000,
    "amount": 1318750000.00
  },
  "message": "获取 000001 行情成功"
}
```

---

### 3.2 实时行情快照 - 批量

**端点**: `GET /api/v1/market/quote`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `codes` | string | 是 | 股票代码列表，逗号分隔，如 `000001,600519,300750` |
| `names` | boolean | 否 | 是否返回股票名称，默认 `true` |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "total": 3,
    "quotes": [
      {
        "code": "000001",
        "fullCode": "000001.SZ",
        "name": "平安银行",
        "close": 10.55,
        "changePct": 0.67
      },
      {
        "code": "600519",
        "fullCode": "600519.SH",
        "name": "贵州茅台",
        "close": 1850.00,
        "changePct": -1.23
      }
    ]
  },
  "message": "获取 3 只股票行情成功"
}
```

---

### 3.3 K线数据

**端点**: `GET /api/v1/market/kline/{code}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 股票代码 |

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `period` | string | 否 | `1d` | K线周期：`1m`, `5m`, `15m`, `30m`, `1h`, `1d`, `1w`, `1mon` |
| `count` | integer | 否 | `100` | 返回K线数量（最多 1000） |
| `start` | string | 否 | - | 开始日期 YYYYMMDD |
| `end` | string | 否 | - | 结束日期 YYYYMMDD |
| `download` | boolean | 否 | `true` | 是否先下载历史数据（确保缓存） |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "code": "000001",
    "fullCode": "000001.SZ",
    "name": "平安银行",
    "period": "1d",
    "count": 100,
    "kline": [
      {
        "date": "20260501",
        "open": 10.50,
        "high": 10.68,
        "low": 10.42,
        "close": 10.55,
        "volume": 125000000,
        "amount": 1318750000.00
      },
      {
        "date": "20260502",
        "open": 10.55,
        "high": 10.70,
        "low": 10.50,
        "close": 10.62,
        "volume": 98765000,
        "amount": 1045230000.00
      }
    ]
  },
  "message": "获取 000001 100 条 1d K线"
}
```

---

### 3.4 五档盘口 - 单只

**端点**: `GET /api/v1/market/tick/{code}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 股票代码 |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "code": "000001",
    "fullCode": "000001.SZ",
    "name": "平安银行",
    "lastPrice": 10.55,
    "open": 10.50,
    "high": 10.68,
    "low": 10.42,
    "preClose": 10.48,
    "volume": 125000000,
    "amount": 1318750000.00,
    "bidPrice": [10.55, 10.54, 10.53, 10.52, 10.51],
    "bidVol": [5000, 8000, 12000, 15000, 20000],
    "askPrice": [10.56, 10.57, 10.58, 10.59, 10.60],
    "askVol": [6000, 9000, 11000, 14000, 18000],
    "time": "20260511153000"
  },
  "message": "获取 000001 五档盘口"
}
```

**字段说明**:

| 字段 | 说明 |
|------|------|
| `bidPrice[0]` | 买一价（最高买入挂单价） |
| `bidVol[0]` | 买一量（买一价的挂单量） |
| `askPrice[0]` | 卖一价（最低卖出挂单价） |
| `askVol[0]` | 卖一量（卖一价的挂单量） |

---

### 3.5 五档盘口 - 批量

**端点**: `GET /api/v1/market/tick`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `codes` | string | 是 | 股票代码列表，逗号分隔 |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "total": 2,
    "ticks": [
      {
        "code": "000001",
        "lastPrice": 10.55,
        "bidPrice": [10.55, 10.54, 10.53, 10.52, 10.51],
        "bidVol": [5000, 8000, 12000, 15000, 20000],
        "askPrice": [10.56, 10.57, 10.58, 10.59, 10.60],
        "askVol": [6000, 9000, 11000, 14000, 18000]
      },
      {
        "code": "600519",
        "lastPrice": 1850.00,
        "bidPrice": [1850.00, 1849.00, 1848.00, 1847.00, 1846.00],
        "bidVol": [100, 150, 200, 250, 300],
        "askPrice": [1851.00, 1852.00, 1853.00, 1854.00, 1855.00],
        "askVol": [120, 180, 220, 280, 350]
      }
    ]
  },
  "message": "获取 2 只股票五档盘口"
}
```

---

### 3.6 股票列表

**端点**: `GET /api/v1/market/stock-list`

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `sync` | boolean | 否 | `true` | 是否先同步板块数据（首次较慢） |
| `market` | string | 否 | `all` | 市场筛选：`sh`, `sz`, `bj`, `all` |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "total": 5200,
    "stocks": [
      {
        "code": "000001",
        "fullCode": "000001.SZ",
        "name": "平安银行",
        "market": "SZ",
        "marketName": "深圳证券交易所"
      },
      {
        "code": "600519",
        "fullCode": "600519.SH",
        "name": "贵州茅台",
        "market": "SH",
        "marketName": "上海证券交易所"
      }
    ],
    "synced": true,
    "blockCount": 6500
  },
  "message": "获取 5200 只股票列表"
}
```

---

### 3.7 板块列表

**端点**: `GET /api/v1/market/blocks`

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `keyword` | string | 否 | - | 关键词筛选 |
| `type` | string | 否 | `all` | 板块类型：`industry`, `concept`, `index`, `all` |
| `sync` | boolean | 否 | `false` | 强制重新同步板块数据 |
| `limit` | integer | 否 | `200` | 返回数量上限 |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "total": 6500,
    "returned": 200,
    "blocks": [
      "沪深300成分",
      "上证50成分",
      "银行业",
      "白酒概念",
      "新能源"
    ]
  },
  "message": "获取 200 个板块（共 6500 个）"
}
```

---

### 3.8 板块成分股

**端点**: `GET /api/v1/market/block-stocks`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `block` | string | 是 | 板块名称，如 `沪深300成分` |
| `limit` | integer | 否 | 返回数量上限，默认 `50` |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "block": "沪深300成分",
    "total": 300,
    "stocks": [
      {
        "code": "600519",
        "fullCode": "600519.SH",
        "name": "贵州茅台"
      },
      {
        "code": "000001",
        "fullCode": "000001.SZ",
        "name": "平安银行"
      }
    ]
  },
  "message": "获取 沪深300成分 板块成分股 300 只"
}
```

---

### 3.9 财务数据

**端点**: `GET /api/v1/market/finance/{code}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 股票代码 |

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `tables` | string | 否 | `all` | 财务表：`Income`, `Balance`, `CashFlow`, `Capital`, `PershareIndex`, `all` |
| `limit` | integer | 否 | `4` | 返回报告期数（最近N期） |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "code": "000001",
    "fullCode": "000001.SZ",
    "name": "平安银行",
    "tables": {
      "Income": [
        {
          "reportDate": "2025Q4",
          "revenue": 125000000000,
          "netProfit": 45000000000
        }
      ],
      "Balance": [
        {
          "reportDate": "2025Q4",
          "totalAssets": 5500000000000,
          "totalLiabilities": 5000000000000,
          "totalEquity": 500000000000
        }
      ]
    }
  },
  "message": "获取 000001 财务数据"
}
```

---

### 3.10 大盘指数概览

**端点**: `GET /api/v1/market/market-overview`

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "indexes": [
      {
        "code": "000001",
        "fullCode": "000001.SH",
        "name": "上证指数",
        "close": 3250.50,
        "change": 25.30,
        "changePct": 0.78,
        "volume": 250000000000,
        "amount": 3.2e12
      },
      {
        "code": "399001",
        "fullCode": "399001.SZ",
        "name": "深证成指",
        "close": 10500.00,
        "change": -50.00,
        "changePct": -0.47
      },
      {
        "code": "399006",
        "fullCode": "399006.SZ",
        "name": "创业板指",
        "close": 2100.00,
        "change": 15.00,
        "changePct": 0.72
      }
    ]
  },
  "message": "大盘指数概览"
}
```

---

### 3.11 交易日历

**端点**: `GET /api/v1/market/trading-dates`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `start` | string | 是 | 开始日期 YYYYMMDD |
| `end` | string | 是 | 结束日期 YYYYMMDD |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "start": "20260101",
    "end": "20260511",
    "tradingDays": [
      "20260102",
      "20260103",
      "20260104",
      "20260105",
      "..."
    ],
    "count": 85
  },
  "message": "获取交易日历"
}
```

---

### 3.12 股票详情

**端点**: `GET /api/v1/market/instrument/{code}`

**路径参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 股票代码 |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "code": "000001",
    "fullCode": "000001.SZ",
    "name": "平安银行",
    "type": "股票",
    "exchange": "SZSE",
    "exchangeName": "深圳证券交易所",
    "listedDate": "19910403",
    "delisted": false
  },
  "message": "获取 000001 详情"
}
```

---

### 3.13 实时订阅（同步模式）

**端点**: `POST /api/v1/market/subscribe`

**说明**: 此接口为**同步阻塞模式**。Server 在订阅期间阻塞等待，返回订阅期间收集的所有 tick 数据。不支持 WebSocket 实时推送（如有需要可后续扩展）。

**请求体**:

```json
{
  "codes": ["000001", "600519"],
  "seconds": 5
}
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `codes` | array | 是 | - | 股票代码列表 |
| `seconds` | integer | 否 | `1` | 订阅时长（秒），Server 阻塞等待此时长后返回 |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "subscribed": ["000001", "600519"],
    "duration": 5,
    "tickCount": 10,
    "ticks": [
      {
        "code": "000001",
        "lastPrice": 10.55,
        "bidPrice": [10.55, 10.54, 10.53, 10.52, 10.51],
        "askPrice": [10.56, 10.57, 10.58, 10.59, 10.60],
        "bidVol": [5000, 8000, 12000, 15000, 20000],
        "askVol": [6000, 9000, 11000, 14000, 18000],
        "time": "20260511153005"
      },
      {
        "code": "000001",
        "lastPrice": 10.56,
        "bidPrice": [10.56, 10.55, 10.54, 10.53, 10.52],
        "askPrice": [10.57, 10.58, 10.59, 10.60, 10.61],
        "bidVol": [5500, 8500, 12500, 15500, 20500],
        "askVol": [6500, 9500, 11500, 14500, 18500],
        "time": "20260511153006"
      }
    ]
  },
  "message": "订阅 2 只股票 5 秒，收集 10 个 tick"
}

---

## 4. 账户接口 (Account)

**Base URL**: `/api/v1/account`

**前置要求**: 需在 `config.json` 配置 `account_id` 和 `userdata_path`，且 QMT 已开启「极速策略交易」功能。

### 4.1 资产信息

**端点**: `GET /api/v1/account/asset`

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "accountId": "****1234",
    "accountType": "STOCK",
    "cash": 500000.00,
    "frozenCash": 10000.00,
    "marketValue": 2000000.00,
    "totalAsset": 2500000.00
  },
  "message": "资产信息"
}
```

**字段说明**:

| 字段 | 说明 |
|------|------|
| `cash` | 可用资金 |
| `frozenCash` | 冻结资金（委托占用） |
| `marketValue` | 持仓市值 |
| `totalAsset` | 总资产 = cash + frozenCash + marketValue |

---

### 4.2 持仓查询

**端点**: `GET /api/v1/account/positions`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 否 | 查询指定股票持仓（不传则返回全部） |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "positions": [
      {
        "code": "600519",
        "fullCode": "600519.SH",
        "name": "贵州茅台",
        "volume": 1000,
        "canUseVolume": 800,
        "frozenVolume": 200,
        "yesterdayVolume": 1000,
        "onRoadVolume": 0,
        "openPrice": 1800.00,
        "marketValue": 1850000.00
      }
    ],
    "total": 1
  },
  "message": "持仓查询"
}
```

**字段说明**:

| 字段 | 说明 |
|------|------|
| `volume` | 持仓总量 |
| `canUseVolume` | 可卖数量（未冻结） |
| `frozenVolume` | 冻结数量（委托卖出占用） |
| `yesterdayVolume` | 昨夜拥股（T-1 持仓） |
| `onRoadVolume` | 在途股份（买入未成交） |
| `openPrice` | 平均建仓成本 |

---

### 4.3 委托查询

**端点**: `GET /api/v1/account/orders`

**查询参数**:

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `cancelable_only` | boolean | 否 | `false` | 仅返回可撤委托 |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "orders": [
      {
        "orderId": 123456789,
        "orderSysId": "202605111530001",
        "code": "000001",
        "fullCode": "000001.SZ",
        "name": "平安银行",
        "orderType": 23,
        "orderTypeName": "买入",
        "orderVolume": 1000,
        "tradedVolume": 500,
        "tradedPrice": 10.55,
        "price": 10.60,
        "priceType": 11,
        "orderStatus": 55,
        "orderStatusName": "部成",
        "orderTime": "20260511153000",
        "strategyName": "",
        "orderRemark": "",
        "cancelable": true
      }
    ],
    "total": 1
  },
  "message": "今日委托查询"
}
```

**订单状态说明**:

| 状态码 | 含义 |
|------|------|
| 48 | 未报 |
| 49 | 待报 |
| 50 | 已报 |
| 51 | 已报待撤 |
| 52 | 部成待撤 |
| 53 | 部撤 |
| 54 | 已撤 |
| 55 | 部成 |
| 56 | 已成 |
| 57 | 废单 |
| 255 | 未知 |

---

### 4.4 成交查询

**端点**: `GET /api/v1/account/trades`

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "trades": [
      {
        "tradeId": "202605111530001",
        "orderId": 123456789,
        "orderSysId": "202605111530001",
        "code": "000001",
        "fullCode": "000001.SZ",
        "name": "平安银行",
        "orderType": 23,
        "orderTypeName": "买入",
        "tradedPrice": 10.55,
        "tradedVolume": 500,
        "tradedAmount": 5275.00,
        "tradedTime": "20260511153001"
      }
    ],
    "total": 1
  },
  "message": "今日成交查询"
}
```

---

## 5. 交易接口 (Trade)

**Base URL**: `/api/v1/trade`

**前置要求**: 同账户接口，且需在请求中带 `confirm=true` 才真正下单。

### 5.1 买入下单

**端点**: `POST /api/v1/trade/buy`

**请求体**:

```json
{
  "code": "000001",
  "volume": 1000,
  "priceType": "FIX",
  "price": 10.55,
  "strategyName": "",
  "orderRemark": "",
  "confirm": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 股票代码 |
| `volume` | integer | 是 | 买入数量（必须是100的整数倍） |
| `priceType` | string | 是 | 报价类型，见下表 |
| `price` | float | 条件必填 | 指定价格（priceType=FIX时必填） |
| `strategyName` | string | 否 | 策略名称（日志用） |
| `orderRemark` | string | 否 | 委托备注 |
| `confirm` | boolean | 否 | `true` = 真正下单，`false` = 仅预演 |

**报价类型**:

| 值 | 含义 |
|------|------|
| `FIX` | 指定价（需同时传 price） |
| `LATEST` | 最新价 |
| `SH_CONVERT_5_CANCEL` | 上海市价五档即成剩撤 |
| `SH_CONVERT_5_LIMIT` | 上海市价五档即成限 |
| `PEER_PRICE_FIRST` | 对手方最优 |
| `MINE_PRICE_FIRST` | 本方最优 |
| `SZ_INSTBUSI_RESTCANCEL` | 深圳即时成交剩余撤销 |
| `SZ_CONVERT_5_CANCEL` | 深圳五档即成剩撤 |
| `SZ_FULL_OR_CANCEL` | 深圳全额成交或撤销 |

**响应示例（预演）**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "dryRun": true,
    "action": "BUY",
    "code": "000001",
    "fullCode": "000001.SZ",
    "volume": 1000,
    "priceType": "FIX",
    "price": 10.55,
    "estimatedAmount": 10550.00,
    "note": "未传 confirm=true，仅预演，未发送到 QMT"
  },
  "message": "预演（未下单）"
}
```

**响应示例（真正下单）**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "dryRun": false,
    "action": "BUY",
    "code": "000001",
    "fullCode": "000001.SZ",
    "volume": 1000,
    "priceType": "FIX",
    "price": 10.55,
    "orderId": 123456789,
    "orderTime": "20260511153000"
  },
  "message": "买入委托已提交，orderId=123456789"
}
```

---

### 5.2 卖出下单

**端点**: `POST /api/v1/trade/sell`

**请求体**:

```json
{
  "code": "000001",
  "volume": 500,
  "priceType": "LATEST",
  "confirm": false
}
```

参数同买入。

---

### 5.3 撤单

**端点**: `POST /api/v1/trade/cancel`

**请求体**:

```json
{
  "orderId": 123456789,
  "confirm": false
}
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `orderId` | integer | 是 | 委托编号（buy/sell 返回的 orderId） |
| `confirm` | boolean | 否 | `true` = 真正撤单 |

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "dryRun": false,
    "action": "CANCEL",
    "orderId": 123456789,
    "cancelResult": 0,
    "cancelResultName": "撤单成功"
  },
  "message": "撤单成功"
}
```

**撤单返回码**:

| 值 | 含义 |
|------|------|
| 0 | 撤单成功 |
| -1 | 托已完成，不可撤 |
| -2 | 未找到对应委托 |
| -3 | 账号未登录 |

---

## 6. 系统接口 (System)

**Base URL**: `/api/v1/system`

### 6.1 健康检查

**端点**: `GET /api/v1/system/health`

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "status": "healthy",
    "qmtConnected": true,
    "xtquantAvailable": true,
    "accountConfigured": true
  },
  "message": "系统健康"
}
```

---

### 6.2 环境诊断

**端点**: `GET /api/v1/system/doctor`

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "checks": [
      {
        "name": "平台检查",
        "ok": true,
        "detail": "Windows"
      },
      {
        "name": "Python版本",
        "ok": true,
        "detail": "3.10.11"
      },
      {
        "name": "xtquant路径配置",
        "ok": true,
        "detail": "D:\\software\\QMT\\bin.x64\\Lib\\site-packages"
      },
      {
        "name": "xtquant导入",
        "ok": true,
        "detail": "from xtquant import xtdata"
      },
      {
        "name": "QMT终端连接",
        "ok": true,
        "detail": "上证指数行情获取成功"
      },
      {
        "name": "账号配置",
        "ok": true,
        "detail": "account_id: ****1234"
      }
    ],
    "pass": 6,
    "fail": 0,
    "overall": "pass"
  },
  "message": "诊断完成：全部通过"
}
```

---

### 6.3 Server 状态

**端点**: `GET /api/v1/system/status`

**响应示例**:

```json
{
  "success": true,
  "timestamp": "2026-05-11T15:30:00",
  "data": {
    "version": "1.0.0",
    "uptime": "2h30m",
    "startedAt": "2026-05-11T13:00:00",
    "requestsTotal": 1250,
    "requestsSuccess": 1248,
    "requestsFailed": 2,
    "lastError": "2026-05-11T14:00:00 QMT_NOT_CONNECTED"
  },
  "message": "Server 状态"
}
```

---

## 7. 错误码

| 错误码 | 含义 | HTTP 状态码 |
|--------|------|-------------|
| `SUCCESS` | 成功 | 200 |
| `QMT_NOT_CONNECTED` | QMT 终端未运行或连接失败 | 503 |
| `XTQUANT_IMPORT_FAILED` | xtquant 模块导入失败 | 500 |
| `INVALID_CODE` | 无效的股票代码 | 400 |
| `INVALID_PARAMETERS` | 参数错误 | 400 |
| `RATE_LIMITED` | 请求频率超限 | 429 |
| `ACCOUNT_NOT_CONFIGURED` | 账号未配置 | 503 |
| `ORDER_FAILED` | 下单失败 | 500 |
| `CANCEL_FAILED` | 撤单失败 | 500 |
| `INTERNAL_ERROR` | 内部错误 | 500 |

---

## 8. 配置

### 8.1 Server 配置文件

**路径**: `qmt_server/config.json`

```json
{
  "host": "0.0.0.0",
  "port": 8080,
  "xtquant_path": "D:\\software\\QMT\\bin.x64\\Lib\\site-packages",
  "userdata_path": "D:\\software\\QMT\\userdata_mini",
  "account_id": "12345678",
  "account_type": "STOCK",
  "log_level": "INFO",
  "rate_limit": {
    "enabled": true,
    "requests_per_minute": 60
  }
}
```

### 8.2 环境变量覆盖

| 变量 | 说明 |
|------|------|
| `QMT_XTQUANT_PATH` | xtquant 路径 |
| `QMT_USERDATA_PATH` | userdata 路径 |
| `QMT_ACCOUNT_ID` | 账号 ID |
| `QMT_SERVER_PORT` | Server 端口 |
| `QMT_LOG_LEVEL` | 日志级别 |

---

## 9. TradingAgents-CN 客户端适配

### 9.1 配置变更

TradingAgents-CN 需新增配置项：

```python
# app/core/config.py
QMT_SERVER_URL: str = Field(default="http://localhost:8080")
QMT_SERVER_TIMEOUT: int = Field(default=30)
QMT_SERVER_ENABLED: bool = Field(default=True)  # 是否使用远程 Server
```

### 9.2 Adapter 变更

`qmt_adapter.py` 从本地调用改为 HTTP 调用：

```python
class QMTAdapter(DataSourceAdapter):
    def __init__(self):
        self.server_url = settings.QMT_SERVER_URL
        self.timeout = settings.QMT_SERVER_TIMEOUT
    
    def is_available(self) -> bool:
        # HTTP 健康检查替代本地检查
        response = requests.get(f"{self.server_url}/api/v1/system/health")
        return response.json()["data"]["qmtConnected"]
    
    def get_realtime_quotes(self) -> Optional[Dict]:
        response = requests.get(f"{self.server_url}/api/v1/market/quote?codes=all")
        return response.json()["data"]["quotes"]
```

---

## 10. 部署说明

### 10.1 Server 启动

```bash
# Windows 上运行
cd qmt_server
python main.py

# 或使用 uvicorn
uvicorn main:app --host 0.0.0.0 --port 8080
```

### 10.2 前置条件

1. QMT 终端已安装并运行
2. Python 3.10/3.11 环境
3. xtquant 路径配置正确
4. （交易功能）账号配置完成，QMT 已开启「极速策略交易」

---

## 11. 安全考虑

1. **认证**: Server 可配置 API Key 认证（可选）
2. **限流**: 默认 60 requests/minute，防止过度请求
3. **日志**: 所有交易操作记录到日志文件
4. **预演机制**: 下单默认不执行，需 `confirm=true`

---

## 12. 文件结构

```
TradingAgents-CN/
├── qmt_server/                    ← Server 端（独立部署）
│   ├── main.py                    (FastAPI 入口)
│   ├── config.py                  (配置加载)
│   ├── routers/
│   │   ├── market.py              (行情接口)
│   │   ├── account.py             (账户接口)
│   │   ├── trade.py               (交易接口)
│   │   └── system.py              (系统接口)
│   ├── services/
│   │   ├── xtquant_service.py     (xtdata 封装)
│   │   └── trade_service.py       (xttrader 封装)
│   ├── models/
│   │   └── schemas.py             (Pydantic 模型)
│   ├── middleware/
│   │   └── rate_limit.py          (限流中间件)
│   ├── scripts/
│   │   └── config.json            (QMT 配置)
│   └── requirements.txt
│
├── app/services/data_sources/
│   └── qmt_adapter.py             ← 修改为 HTTP Client
│
└── docs/superpowers/specs/
    └── 2026-05-11-qmt-server-design.md  (本文档)
```