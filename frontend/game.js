/**
 * game.js - RPG 战斗系统前端逻辑
 * 
 * 负责：
 * 1. WebSocket 通信
 * 2. UI 渲染与更新
 * 3. 用户交互处理
 */

// ==================== 消息类型常量 ====================
const ServerMsgType = {
    INIT_STATE: "INIT_STATE",
    UPDATE_HP: "UPDATE_HP",
    UPDATE_MP: "UPDATE_MP",
    UNIT_DIED: "UNIT_DIED",
    LOG: "LOG",
    TURN_START: "TURN_START",
    DAMAGE: "DAMAGE",
    HEAL: "HEAL",
    BATTLE_END: "BATTLE_END",
    REQUEST_ACTION: "REQUEST_ACTION",
    REQUEST_SKILL: "REQUEST_SKILL",
    REQUEST_TARGET: "REQUEST_TARGET"
};

const ClientMsgType = {
    START_BATTLE: "START_BATTLE",
    SELECT_CATEGORY: "SELECT_CATEGORY",
    SELECT_SKILL: "SELECT_SKILL",
    SELECT_TARGET: "SELECT_TARGET",
    RESTART: "RESTART"
};

// ==================== 游戏状态 ====================
class GameState {
    constructor() {
        this.allies = [];
        this.enemies = [];
        this.unitsMap = {};
        this.currentActorId = null;
        this.turnNumber = 0;
        this.isWaitingForInput = false;
        this.selectableTargets = [];
        this.selectedTargets = [];
        this.currentSkillId = null;
        this.isAoe = false;
    }

    reset() {
        this.allies = [];
        this.enemies = [];
        this.unitsMap = {};
        this.currentActorId = null;
        this.turnNumber = 0;
        this.isWaitingForInput = false;
        this.selectableTargets = [];
        this.selectedTargets = [];
        this.currentSkillId = null;
        this.isAoe = false;
    }

    updateUnit(unitId, updates) {
        if (this.unitsMap[unitId]) {
            Object.assign(this.unitsMap[unitId], updates);
        }
    }

    getUnit(unitId) {
        return this.unitsMap[unitId];
    }
}

// ==================== WebSocket 客户端 ====================
class GameClient {
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
            case ServerMsgType.BATTLE_END:
                this.handleBattleEnd(data);
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

    handleInitState(data) {
        this.state.reset();
        
        // 保存单位数据
        data.allies.forEach(unit => {
            this.state.allies.push(unit);
            this.state.unitsMap[unit.id] = unit;
        });
        
        data.enemies.forEach(unit => {
            this.state.enemies.push(unit);
            this.state.unitsMap[unit.id] = unit;
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
    }

    handleRequestAction(data) {
        this.state.isWaitingForInput = true;
        this.ui.showActionSelection(data.actor_name, data.categories);
    }

    handleRequestSkill(data) {
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

    startBattle() {
        this.send(ClientMsgType.START_BATTLE);
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
        this.send(ClientMsgType.RESTART);
        this.ui.hideBattleEndModal();
    }
}

// ==================== UI 管理器 ====================
class GameUI {
    constructor(client) {
        this.client = client;
        this.elements = {
            connectionStatus: document.getElementById('connectionStatus'),
            allyUnits: document.getElementById('allyUnits'),
            enemyUnits: document.getElementById('enemyUnits'),
            turnIndicator: document.getElementById('turnIndicator'),
            actionPanel: document.getElementById('actionPanel'),
            actionTitle: document.getElementById('actionTitle'),
            actionContent: document.getElementById('actionContent'),
            battleLog: document.getElementById('battleLog'),
            battleEndModal: document.getElementById('battleEndModal'),
            modalIcon: document.getElementById('modalIcon'),
            modalTitle: document.getElementById('modalTitle'),
            modalMessage: document.getElementById('modalMessage')
        };
        
        this.bindEvents();
    }

    bindEvents() {
        // 开始战斗按钮
        document.getElementById('startBattleBtn')?.addEventListener('click', () => {
            this.client.startBattle();
        });

        // 重新开始按钮
        document.getElementById('restartBtn')?.addEventListener('click', () => {
            this.client.restart();
        });

        // 清空日志按钮
        document.getElementById('clearLogBtn')?.addEventListener('click', () => {
            this.elements.battleLog.innerHTML = '';
        });
    }

    setConnectionStatus(connected) {
        const dot = this.elements.connectionStatus.querySelector('.status-dot');
        const text = this.elements.connectionStatus.querySelector('.status-text');
        
        if (connected) {
            dot.classList.add('connected');
            text.textContent = '已连接';
        } else {
            dot.classList.remove('connected');
            text.textContent = '未连接';
        }
    }

    // ==================== 单位渲染 ====================

    renderUnits() {
        this.elements.allyUnits.innerHTML = '';
        this.elements.enemyUnits.innerHTML = '';
        
        this.client.state.allies.forEach(unit => {
            const card = this.createUnitCard(unit);
            this.elements.allyUnits.appendChild(card);
        });
        
        this.client.state.enemies.forEach(unit => {
            const card = this.createUnitCard(unit);
            this.elements.enemyUnits.appendChild(card);
        });
    }

    createUnitCard(unit) {
        const card = document.createElement('div');
        card.className = 'unit-card';
        card.id = `unit-${unit.id}`;
        card.dataset.unitId = unit.id;
        
        const hpPercent = (unit.current_hp / unit.max_hp) * 100;
        const mpPercent = (unit.current_mp / unit.max_mp) * 100;
        
        card.innerHTML = `
            <div class="unit-name">${unit.name}</div>
            <div class="resource-bar hp-bar">
                <div class="bar-fill" style="width: ${hpPercent}%"></div>
                <span class="bar-text">${unit.current_hp} / ${unit.max_hp}</span>
            </div>
            <div class="resource-bar mp-bar">
                <div class="bar-fill" style="width: ${mpPercent}%"></div>
                <span class="bar-text">${unit.current_mp} / ${unit.max_mp}</span>
            </div>
        `;
        
        if (unit.is_dead) {
            card.classList.add('dead');
        }
        
        return card;
    }

    updateUnitCard(unitId) {
        const unit = this.client.state.getUnit(unitId);
        if (!unit) return;
        
        const card = document.getElementById(`unit-${unitId}`);
        if (!card) return;
        
        const hpPercent = (unit.current_hp / unit.max_hp) * 100;
        const hpBar = card.querySelector('.hp-bar .bar-fill');
        const hpText = card.querySelector('.hp-bar .bar-text');
        
        if (hpBar) hpBar.style.width = `${hpPercent}%`;
        if (hpText) hpText.textContent = `${unit.current_hp} / ${unit.max_hp}`;
        
        const mpPercent = (unit.current_mp / unit.max_mp) * 100;
        const mpBar = card.querySelector('.mp-bar .bar-fill');
        const mpText = card.querySelector('.mp-bar .bar-text');
        
        if (mpBar) mpBar.style.width = `${mpPercent}%`;
        if (mpText) mpText.textContent = `${unit.current_mp} / ${unit.max_mp}`;
        
        if (unit.is_dead) {
            card.classList.add('dead');
        }
    }

    setActiveUnit(unitId) {
        // 移除所有活跃状态
        document.querySelectorAll('.unit-card.active').forEach(card => {
            card.classList.remove('active');
        });
        
        // 设置当前活跃
        const card = document.getElementById(`unit-${unitId}`);
        if (card) {
            card.classList.add('active');
        }
    }

    setTurnIndicator(text) {
        this.elements.turnIndicator.textContent = text;
    }

    // ==================== 操作面板 ====================

    showActionSelection(actorName, categories) {
        this.elements.actionTitle.textContent = `${actorName} - 选择行动`;
        
        let html = '';
        categories.forEach(cat => {
            const className = cat.id.toLowerCase();
            html += `<button class="btn btn-action ${className}" data-category="${cat.id}">${cat.name}</button>`;
        });
        
        this.elements.actionContent.innerHTML = html;
        
        // 绑定事件
        this.elements.actionContent.querySelectorAll('[data-category]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.client.selectCategory(btn.dataset.category);
            });
        });
    }

    showSkillSelection(categoryName, hasBasicAttack, skills) {
        this.elements.actionTitle.textContent = `选择${categoryName}`;
        
        let html = '<button class="btn btn-back" data-back>← 返回</button>';
        
        if (hasBasicAttack) {
            html += `<button class="btn btn-action skill-btn" data-skill="null">
                <span class="skill-name">普通攻击</span>
            </button>`;
        }
        
        skills.forEach(skill => {
            const costText = skill.cost_mp ? `MP: ${skill.cost_mp}` : '';
            // 显示具体的不可用原因，如果有的话
            let extraInfo = '';
            if (skill.current_cd > 0) {
                extraInfo = `<span class="skill-status cd">CD: ${skill.current_cd}</span>`;
            } else if (!skill.is_usable) {
                extraInfo = `<span class="skill-status warning">${skill.unusable_reason}</span>`;
            }

            // 如果 is_usable 为 false，则禁用按钮
            const disabled = !skill.is_usable ? 'disabled' : '';
            
            html += `<button class="btn btn-action skill-btn" data-skill="${skill.id}" ${disabled}>
                <div class="skill-top">
                    <span class="skill-name">${skill.name}</span>
                    <span class="skill-cost">${costText}</span>
                </div>
                ${extraInfo}
            </button>`;
        });
        
        this.elements.actionContent.innerHTML = html;
        
        // 绑定事件
        this.elements.actionContent.querySelector('[data-back]')?.addEventListener('click', () => {
            this.client.selectSkillBack();
        });
        
        this.elements.actionContent.querySelectorAll('[data-skill]').forEach(btn => {
            if (!btn.disabled) {
                btn.addEventListener('click', () => {
                    const skillId = btn.dataset.skill === 'null' ? null : btn.dataset.skill;
                    this.client.selectSkill(skillId);
                });
            }
        });
    }

    showTargetSelection(skillName, isAoe, targets) {
        this.elements.actionTitle.textContent = `选择 ${skillName} 的目标`;
        
        // 设置目标卡片为可选状态
        targets.forEach(target => {
            const card = document.getElementById(`unit-${target.id}`);
            if (card) {
                card.classList.add('selectable');
                if (isAoe) {
                    card.classList.add('selected');
                }
            }
        });
        
        let html = '<button class="btn btn-back" data-back>← 返回</button>';
        
        if (isAoe) {
            html += `<button class="btn btn-confirm" data-confirm>确认释放</button>`;
            html += `<p style="margin-top: 8px; color: var(--text-secondary);">将作用于: ${targets.map(t => t.name).join(', ')}</p>`;
        } else {
            html += `<p style="margin-top: 8px; color: var(--text-secondary);">点击选择一个目标</p>`;
        }
        
        this.elements.actionContent.innerHTML = html;
        
        // 绑定事件
        this.elements.actionContent.querySelector('[data-back]')?.addEventListener('click', () => {
            this.client.selectTargetBack();
        });
        
        if (isAoe) {
            this.elements.actionContent.querySelector('[data-confirm]')?.addEventListener('click', () => {
                this.client.confirmTargets(targets.map(t => t.id));
            });
        } else {
            // 单体技能：点击目标卡片
            targets.forEach(target => {
                const card = document.getElementById(`unit-${target.id}`);
                if (card) {
                    const handler = () => {
                        this.client.confirmTargets([target.id]);
                    };
                    card.addEventListener('click', handler);
                    card.dataset.targetHandler = 'true';
                }
            });
        }
    }

    clearTargetSelection() {
        document.querySelectorAll('.unit-card.selectable').forEach(card => {
            card.classList.remove('selectable', 'selected');
        });
        this.client.state.selectableTargets = [];
        this.client.state.selectedTargets = [];
    }

    clearActionPanel() {
        this.elements.actionTitle.textContent = '等待中...';
        this.elements.actionContent.innerHTML = '<p style="color: var(--text-secondary);">请等待...</p>';
    }

    // ==================== 日志 ====================

    addLog(message, type = 'system') {
        const entry = document.createElement('p');
        entry.className = `log-entry log-${type}`;
        entry.textContent = message;
        
        this.elements.battleLog.appendChild(entry);
        this.elements.battleLog.scrollTop = this.elements.battleLog.scrollHeight;
    }

    // ==================== 伤害飘字 ====================

    showDamageFloat(unitId, amount, type, isCrit) {
        const card = document.getElementById(`unit-${unitId}`);
        if (!card) return;
        
        const float = document.createElement('div');
        float.className = `damage-float ${type} ${isCrit ? 'crit' : ''}`;
        float.textContent = (type === 'heal' ? '+' : '-') + amount;
        
        // 设置位置
        const rect = card.getBoundingClientRect();
        float.style.left = `${rect.left + rect.width / 2}px`;
        float.style.top = `${rect.top}px`;
        
        document.body.appendChild(float);
        
        // 动画结束后移除
        setTimeout(() => float.remove(), 1000);
    }

    // ==================== 弹窗 ====================

    showBattleEndModal(isVictory, message) {
        this.elements.modalIcon.textContent = isVictory ? '🏆' : '💀';
        this.elements.modalTitle.textContent = isVictory ? '胜利！' : '战败...';
        this.elements.modalMessage.textContent = message;
        this.elements.battleEndModal.classList.add('show');
    }

    hideBattleEndModal() {
        this.elements.battleEndModal.classList.remove('show');
    }
}

// ==================== 启动 ====================
document.addEventListener('DOMContentLoaded', () => {
    const client = new GameClient();
    client.connect();
    
    // 暴露到全局方便调试
    window.gameClient = client;
});
