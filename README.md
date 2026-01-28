# RPG 战斗系统 - 前后端分离版本

## 项目结构

```
rpg_game_python/
├── backend/                 # Python 后端
│   ├── main.py             # 原始 CLI 版本（保留）
│   ├── run_server.py       # 🚀 WebSocket 服务器启动入口
│   ├── requirements.txt    # Python 依赖
│   ├── rpg_core/           # 核心游戏逻辑（不变）
│   │   ├── enums.py
│   │   ├── models.py
│   │   ├── events.py
│   │   ├── logic.py
│   │   ├── controllers.py
│   │   └── engine.py
│   └── server/             # 网络层（新增）
│       ├── app.py          # FastAPI 应用
│       ├── protocol.py     # 通信协议定义
│       ├── game_bridge.py  # 游戏桥接器
│       └── websocket_controller.py
│
└── frontend/               # JavaScript 前端
    ├── index.html          # 主页面
    ├── styles.css          # 样式
    └── game.js             # 游戏客户端逻辑
```

## 快速开始

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 2. 启动服务器

```bash
cd backend
python run_server.py
```

服务器将在 http://localhost:8000 启动。

### 3. 打开浏览器

访问 http://localhost:8000 即可开始游戏！

## 架构说明

### 通信流程

```
┌─────────────┐   WebSocket    ┌─────────────┐
│   前端 JS   │ <============> │  后端 Python │
│             │                │             │
│ - 渲染 UI   │   JSON 消息    │ - 游戏逻辑   │
│ - 用户交互  │                │ - 战斗计算   │
│ - 动画效果  │                │ - 状态管理   │
└─────────────┘                └─────────────┘
```

### 消息协议

**服务器 -> 客户端 (S2C)**
- `INIT_STATE`: 初始化战斗状态
- `TURN_START`: 回合开始
- `DAMAGE` / `HEAL`: 伤害/治疗事件
- `REQUEST_ACTION`: 请求玩家选择行动类型
- `REQUEST_SKILL`: 请求玩家选择技能
- `REQUEST_TARGET`: 请求玩家选择目标
- `BATTLE_END`: 战斗结束

**客户端 -> 服务器 (C2S)**
- `START_BATTLE`: 开始战斗
- `SELECT_CATEGORY`: 选择行动类型
- `SELECT_SKILL`: 选择技能
- `SELECT_TARGET`: 选择目标
- `RESTART`: 重新开始

### 核心模块说明

#### `GameBridge` (后端)
- 连接 `rpg_core` 核心逻辑与 WebSocket 网络层
- 订阅 `EventBus` 事件，转换为 JSON 发送给前端
- 接收前端指令，驱动战斗流程

#### `WebSocketController` (后端)
- 替代原来的 `HumanCLIController`
- 使用 `asyncio.Future` 实现异步等待玩家输入

#### `GameClient` (前端)
- 管理 WebSocket 连接
- 处理服务器消息
- 发送玩家操作

## 开发说明

### 添加新技能
1. 在 `game_bridge.py` 的 `_create_mock_data()` 中添加技能模板
2. 前端会自动显示新技能

### 添加新事件
1. 在 `protocol.py` 中定义新的消息类型
2. 在 `game_bridge.py` 中订阅并处理事件
3. 在 `game.js` 中添加消息处理器

### 自定义 UI
- 修改 `styles.css` 调整样式
- 修改 `game.js` 中的 `GameUI` 类调整渲染逻辑

## 技术栈

- **后端**: Python 3.10+, FastAPI, WebSocket, Pydantic
- **前端**: 原生 JavaScript (ES6+), CSS3
- **通信**: WebSocket + JSON
