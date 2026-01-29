/**
 * main.js - 程序入口
 * 
 * 负责初始化和组装各模块
 */

import { GameClient } from './network.js';

// 启动应用
document.addEventListener('DOMContentLoaded', () => {
    const client = new GameClient();
    client.connect();
    
    // 暴露到全局方便调试
    window.gameClient = client;
});
