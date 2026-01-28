"""
app.py - FastAPI WebSocket 服务器

提供 WebSocket 端点，管理游戏会话。
"""
import asyncio
import json
from typing import Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from .game_bridge import GameBridge
from .protocol import ClientMsgType

app = FastAPI(title="RPG Battle Server")

# 存储活跃的游戏会话
active_games: Dict[str, GameBridge] = {}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket 端点：处理游戏通信
    """
    await websocket.accept()
    
    # 创建发送函数
    async def send_message(msg: dict):
        try:
            await websocket.send_json(msg)
        except Exception as e:
            print(f"Send error: {e}")
    
    # 创建游戏桥接器
    game = GameBridge(send_message)
    session_id = str(id(websocket))
    active_games[session_id] = game
    
    try:
        # 等待客户端消息
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            msg_type_str = msg.get("type", "")
            msg_data = msg.get("data", {})
            
            try:
                msg_type = ClientMsgType(msg_type_str)
            except ValueError:
                print(f"Unknown message type: {msg_type_str}")
                continue
            
            # 处理不同类型的消息
            if msg_type == ClientMsgType.START_BATTLE:
                # 初始化并开始战斗
                await game.initialize_battle()
                # 在后台运行战斗循环
                asyncio.create_task(game.run_battle_loop())
            
            elif msg_type == ClientMsgType.RESTART:
                # 重新开始战斗
                await game.initialize_battle()
                asyncio.create_task(game.run_battle_loop())
            
            else:
                # 其他消息转发给游戏桥接器
                game.handle_client_message(msg_type, msg_data)
    
    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # 清理会话
        if session_id in active_games:
            del active_games[session_id]


# 静态文件服务（前端）
# 这里是关键修正：你需要确保 frontend_path 指向正确的 frontend 文件夹
# 假设结构是 rpg_game_python/backend/server/app.py
# 那么 dirname(__file__) 是 .../backend/server
# dirname(dirname(__file__)) 是 .../backend
# dirname(dirname(dirname(__file__))) 是 .../rpg_game_python
# 所以拼接上 "frontend" 是没有问题的
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")

if os.path.exists(frontend_path):
    # 将整个 frontend 目录直接挂载到根路径，这样 html 里的 src="game.js" 就能直接找到文件了
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    print(f"Warning: Frontend path not found at {frontend_path}")


@app.get("/health")
async def health_check():
    return {"status": "ok", "active_games": len(active_games)}
