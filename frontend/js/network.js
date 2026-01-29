/**
 * network.js - WebSocket 通信层
 * 
 * 负责与服务器的连接、消息收发、断线重连
 */

import { ServerMsgType, ClientMsgType } from './constants.js';
import { GameState } from './state.js';
import { GameUI } from './ui.js';

export class GameClient {
    constructor() {
        this.ws = null;
        this.state = new GameState();
        this.ui = new GameUI(this);
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        console.log(`Connecting to ${wsUrl}...`);
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.ui.setConnectionStatus(true);
            this.ui.addLog('已连接到服务器', 'system');
            // 连接后获取战斗列表
            this.send(ClientMsgType.GET_BATTLES);
        };

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);
            this.handleMessage(msg);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.ui.setConnectionStatus(false);
            this.ui.addLog('与服务器断开连接', 'system');
            this.attemptReconnect();
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.ui.addLog('连接错误', 'system');
        };
    }

    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 10000);
            console.log(`Reconnecting in ${delay}ms... (attempt ${this.reconnectAttempts})`);
            setTimeout(() => this.connect(), delay);
        }
    }

    send(type, data = {}) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type, data }));
        }
    }

    handleMessage(msg) {
        console.log('Received:', msg);
        const { type, data } = msg;

        switch (type) {
            case ServerMsgType.BATTLE_LIST:
                this.handleBattleList(data);
                break;
            case ServerMsgType.INIT_STATE:
                this.handleInitState(data);
                break;
            case ServerMsgType.UPDATE_HP:
                this.handleUpdateHP(data);
                break;
            case ServerMsgType.UPDATE_MP:
                this.handleUpdateMP(data);
                break;
            case ServerMsgType.UNIT_DIED:
                this.handleUnitDied(data);
                break;
            case ServerMsgType.LOG:
                this.ui.addLog(data.message, 'system');
                break;
            case ServerMsgType.TURN_START:
                this.handleTurnStart(data);
                break;
            case ServerMsgType.DAMAGE:
                this.handleDamage(data);
                break;
            case ServerMsgType.HEAL:
                this.handleHeal(data);
                break;
            case ServerMsgType.UPDATE_EFFECTS:
                this.handleUpdateEffects(data);
                break;
            case ServerMsgType.EFFECT_APPLIED:
                this.handleEffectApplied(data);
                break;
            case ServerMsgType.EFFECT_REMOVED:
                this.handleEffectRemoved(data);
                break;
            case ServerMsgType.BATTLE_END:
                this.handleBattleEnd(data);
                break;
            case ServerMsgType.RETURN_TO_MENU:
                this.handleReturnToMenu();
                break;
            case ServerMsgType.REQUEST_ACTION:
                this.handleRequestAction(data);
                break;
            case ServerMsgType.REQUEST_SKILL:
                this.handleRequestSkill(data);
                break;
            case ServerMsgType.REQUEST_TARGET:
                this.handleRequestTarget(data);
                break;
        }
    }

    // ==================== 消息处理器 ====================

    handleBattleList(data) {
        this.state.availableBattles = data.battles;
        this.ui.renderBattleList(data.battles);
    }

    handleReturnToMenu() {
        this.state.reset();
        this.ui.showMainMenu();
        this.ui.addLog('返回主菜单', 'system');
    }

    handleInitState(data) {
        this.state.reset();
        
        // 保存单位数据
        data.allies.forEach(unit => {
            this.state.addAlly(unit);
        });
        
        data.enemies.forEach(unit => {
            this.state.addEnemy(unit);
        });
        
        this.state.turnNumber = data.turn_number;
        
        // 渲染 UI
        this.ui.renderUnits();
        this.ui.setTurnIndicator('战斗开始！');
    }

    handleUpdateHP(data) {
        this.state.updateUnit(data.unit_id, {
            current_hp: data.current_hp,
            max_hp: data.max_hp
        });
        this.ui.updateUnitCard(data.unit_id);
    }

    handleUpdateMP(data) {
        this.state.updateUnit(data.unit_id, {
            current_mp: data.current_mp,
            max_mp: data.max_mp
        });
        this.ui.updateUnitCard(data.unit_id);
    }

    handleUpdateEffects(data) {
        // 更新单位的效果列表
        this.state.updateUnit(data.unit_id, {
            effects: data.effects
        });
        this.ui.updateUnitEffects(data.unit_id);
    }

    handleEffectApplied(data) {
        // 效果被施加时的处理（可用于动画等）
        const unit = this.state.getUnit(data.unit_id);
        if (unit) {
            if (!unit.effects) unit.effects = [];
            unit.effects.push(data.effect);
            this.ui.updateUnitEffects(data.unit_id);
            
            const buffType = data.effect.is_buff ? '增益' : '减益';
            this.ui.addLog(`✨ ${data.unit_name} 获得了 ${data.effect.name} (${buffType})`, 'effect');
        }
    }

    handleEffectRemoved(data) {
        // 效果移除时的处理
        const unit = this.state.getUnit(data.unit_id);
        if (unit && unit.effects) {
            unit.effects = unit.effects.filter(e => e.name !== data.effect_name);
            this.ui.updateUnitEffects(data.unit_id);
            this.ui.addLog(`💨 ${data.unit_name} 的 ${data.effect_name} 效果消失了`, 'effect');
        }
    }

    handleUnitDied(data) {
        this.state.updateUnit(data.unit_id, { is_dead: true });
        this.ui.updateUnitCard(data.unit_id);
        this.ui.addLog(`💀 ${data.unit_name} 倒下了！`, 'system');
    }

    handleTurnStart(data) {
        this.state.turnNumber = data.turn_number;
        this.state.currentActorId = data.actor_id;
        
        this.ui.setTurnIndicator(`第 ${data.turn_number} 回合 - ${data.actor_name} 的回合`);
        this.ui.setActiveUnit(data.actor_id);
        this.ui.addLog(`>>> 第 ${data.turn_number} 回合: ${data.actor_name} <<<`, 'turn');
    }

    handleDamage(data) {
        const critText = data.is_crit ? ' (暴击!)' : '';
        this.ui.addLog(
            `⚔️ ${data.source_name} 对 ${data.target_name} 造成 ${data.amount} 点伤害${critText}`,
            data.is_crit ? 'crit' : 'damage'
        );
        this.ui.showDamageFloat(data.target_id, data.amount, 'damage', data.is_crit);
    }

    handleHeal(data) {
        this.ui.addLog(
            `💚 ${data.source_name} 治疗了 ${data.target_name} ${data.amount} 点生命`,
            'heal'
        );
        this.ui.showDamageFloat(data.target_id, data.amount, 'heal', false);
    }

    handleBattleEnd(data) {
        const isVictory = data.winner === 'allies';
        this.ui.showBattleEndModal(isVictory, data.message);
        this.ui.clearActionPanel();
        this.ui.clearTargetSelection();  // 清理目标选择状态
    }

    handleRequestAction(data) {
        this.state.isWaitingForInput = true;
        this.ui.clearTargetSelection();  // 每次新的行动请求时，清理之前的目标选择状态
        this.ui.showActionSelection(data.actor_name, data.categories);
    }

    handleRequestSkill(data) {
        this.ui.clearTargetSelection();  // 返回技能选择时，清理目标选择状态
        this.ui.showSkillSelection(data.category_name, data.has_basic_attack, data.skills);
    }

    handleRequestTarget(data) {
        this.state.currentSkillId = data.skill_id;
        this.state.isAoe = data.is_aoe;
        this.state.selectableTargets = data.targets.map(t => t.id);
        this.state.selectedTargets = data.is_aoe ? [...this.state.selectableTargets] : [];
        
        this.ui.showTargetSelection(data.skill_name, data.is_aoe, data.targets);
    }

    // ==================== 用户操作 ====================

    startBattle(battleId) {
        this.state.currentBattleId = battleId;
        this.ui.showBattleView();
        this.send(ClientMsgType.START_BATTLE, { battle_id: battleId });
    }

    restartBattle() {
        this.send(ClientMsgType.RESTART, { battle_id: this.state.currentBattleId });
    }

    returnToMenu() {
        this.send(ClientMsgType.RETURN_TO_MENU);
    }

    selectCategory(categoryId) {
        this.send(ClientMsgType.SELECT_CATEGORY, { category_id: categoryId });
    }

    selectSkill(skillId) {
        this.send(ClientMsgType.SELECT_SKILL, { skill_id: skillId });
    }

    selectSkillBack() {
        this.send(ClientMsgType.SELECT_SKILL, { back: true });
    }

    confirmTargets(targetIds) {
        this.send(ClientMsgType.SELECT_TARGET, { target_ids: targetIds });
        this.ui.clearTargetSelection();
    }

    selectTargetBack() {
        this.send(ClientMsgType.SELECT_TARGET, { back: true });
        this.ui.clearTargetSelection();
    }

    restart() {
        this.restartBattle();
        this.ui.hideBattleEndModal();
    }
}
