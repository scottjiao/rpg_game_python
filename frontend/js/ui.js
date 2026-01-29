/**
 * ui.js - UI 管理器
 * 
 * 负责所有 DOM 操作和界面渲染
 */

import { ClientMsgType } from './constants.js';

export class GameUI {
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
