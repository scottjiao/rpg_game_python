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
    BATTLE_LIST: "BATTLE_LIST",
    INIT_STATE: "INIT_STATE",
    UPDATE_HP: "UPDATE_HP",
    UPDATE_MP: "UPDATE_MP",
    UPDATE_EFFECTS: "UPDATE_EFFECTS",
    UNIT_DIED: "UNIT_DIED",
    LOG: "LOG",
    TURN_START: "TURN_START",
    DAMAGE: "DAMAGE",
    HEAL: "HEAL",
    EFFECT_APPLIED: "EFFECT_APPLIED",
    EFFECT_REMOVED: "EFFECT_REMOVED",
    BATTLE_END: "BATTLE_END",
    RETURN_TO_MENU: "RETURN_TO_MENU",
    REQUEST_ACTION: "REQUEST_ACTION",
    REQUEST_SKILL: "REQUEST_SKILL",
    REQUEST_TARGET: "REQUEST_TARGET"
};

const ClientMsgType = {
    GET_BATTLES: "GET_BATTLES",
    START_BATTLE: "START_BATTLE",
    SELECT_CATEGORY: "SELECT_CATEGORY",
    SELECT_SKILL: "SELECT_SKILL",
    SELECT_TARGET: "SELECT_TARGET",
    RESTART: "RESTART",
    RETURN_TO_MENU: "RETURN_TO_MENU"
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
        this.currentBattleId = null;
        this.availableBattles = [];
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

// ==================== UI 管理器 ====================
class GameUI {
    constructor(client) {
        this.client = client;
        this.elements = {
            connectionStatus: document.getElementById('connectionStatus'),
            mainMenu: document.getElementById('mainMenu'),
            battleList: document.getElementById('battleList'),
            gameMain: document.getElementById('gameMain'),
            returnMenuBtn: document.getElementById('returnMenuBtn'),
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
        // 返回主菜单按钮
        document.getElementById('returnMenuBtn')?.addEventListener('click', () => {
            this.client.returnToMenu();
        });

        // 重新开始按钮
        document.getElementById('restartBtn')?.addEventListener('click', () => {
            this.client.restart();
        });

        // 弹窗中的返回主菜单按钮
        document.getElementById('backToMenuBtn')?.addEventListener('click', () => {
            this.hideBattleEndModal();
            this.client.returnToMenu();
        });

        // 清空日志按钮
        document.getElementById('clearLogBtn')?.addEventListener('click', () => {
            this.elements.battleLog.innerHTML = '';
        });
    }

    // ==================== 页面切换 ====================

    showMainMenu() {
        this.elements.mainMenu.style.display = 'flex';
        this.elements.gameMain.style.display = 'none';
        this.elements.returnMenuBtn.style.display = 'none';
        // 重新获取战斗列表
        this.client.send(ClientMsgType.GET_BATTLES);
    }

    showBattleView() {
        this.elements.mainMenu.style.display = 'none';
        this.elements.gameMain.style.display = 'flex';
        this.elements.returnMenuBtn.style.display = 'block';
        // 清空日志
        this.elements.battleLog.innerHTML = '<p class="log-entry log-system">战斗开始...</p>';
    }

    renderBattleList(battles) {
        if (!battles || battles.length === 0) {
            this.elements.battleList.innerHTML = '<p class="no-battles">暂无可用战斗</p>';
            return;
        }

        this.elements.battleList.innerHTML = battles.map(battle => `
            <div class="battle-card" data-battle-id="${battle.id}">
                <div class="battle-card-header">
                    <span class="battle-icon">⚔️</span>
                    <h3>${battle.name}</h3>
                </div>
                <p class="battle-description">${battle.description || '无描述'}</p>
                <button class="btn btn-primary start-battle-btn">开始战斗</button>
            </div>
        `).join('');

        // 绑定开始按钮事件
        this.elements.battleList.querySelectorAll('.start-battle-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const battleId = e.target.closest('.battle-card').dataset.battleId;
                this.client.startBattle(battleId);
            });
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
        
        // 生成效果图标 HTML
        const effectsHtml = this.renderEffectIcons(unit.effects || []);
        
        card.innerHTML = `
            <div class="unit-name">${unit.name}</div>
            <div class="unit-effects">${effectsHtml}</div>
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

    renderEffectIcons(effects) {
        if (!effects || effects.length === 0) {
            return '';
        }
        
        return effects.map(effect => {
            const buffClass = effect.is_buff ? 'buff' : 'debuff';
            const stacksText = effect.stacks > 1 ? `×${effect.stacks}` : '';
            const durationText = effect.duration > 0 ? effect.duration : '∞';
            
            return `
                <span class="effect-icon ${buffClass}" 
                      title="${effect.name}: ${effect.description} (${durationText}回合)">
                    ${effect.icon || (effect.is_buff ? '⬆' : '⬇')}${stacksText}
                </span>
            `;
        }).join('');
    }

    updateUnitEffects(unitId) {
        const unit = this.client.state.getUnit(unitId);
        if (!unit) return;
        
        const card = document.getElementById(`unit-${unitId}`);
        if (!card) return;
        
        const effectsContainer = card.querySelector('.unit-effects');
        if (effectsContainer) {
            effectsContainer.innerHTML = this.renderEffectIcons(unit.effects || []);
        }
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
        // 移除所有目标卡片的点击事件监听器
        document.querySelectorAll('.unit-card[data-target-handler]').forEach(card => {
            // 克隆节点来移除所有事件监听器
            const newCard = card.cloneNode(true);
            newCard.removeAttribute('data-target-handler');
            card.parentNode.replaceChild(newCard, card);
        });
        
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
