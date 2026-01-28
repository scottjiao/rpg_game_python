"""
run_server.py - 启动服务器的入口脚本
"""
import uvicorn

if __name__ == "__main__":
    print("=" * 50)
    print("🎮 RPG Battle Server")
    print("=" * 50)
    print("服务器启动中...")
    print("打开浏览器访问: http://localhost:8000")
    print("按 Ctrl+C 停止服务器")
    print("=" * 50)
    
    uvicorn.run(
        "server.app:app",
        host="localhost",
        port=8000,
        reload=True,
        log_level="info"
    )
