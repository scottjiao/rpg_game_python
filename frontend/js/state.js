/**
 * state.js - 游戏状态管理
 * 
 * 纯数据层，不涉及任何 DOM 操作或网络通信
 */

export class GameState {
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

    /**
     * 重置战斗状态（保留战斗列表和当前战斗ID）
     */
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

    /**
     * 更新单位属性
     * @param {string} unitId - 单位ID
     * @param {object} updates - 要更新的属性
     */
    updateUnit(unitId, updates) {
        if (this.unitsMap[unitId]) {
            Object.assign(this.unitsMap[unitId], updates);
        }
    }

    /**
     * 获取单位数据
     * @param {string} unitId - 单位ID
     * @returns {object|undefined} 单位数据
     */
    getUnit(unitId) {
        return this.unitsMap[unitId];
    }

    /**
     * 添加盟友单位
     * @param {object} unit - 单位数据
     */
    addAlly(unit) {
        this.allies.push(unit);
        this.unitsMap[unit.id] = unit;
    }

    /**
     * 添加敌方单位
     * @param {object} unit - 单位数据
     */
    addEnemy(unit) {
        this.enemies.push(unit);
        this.unitsMap[unit.id] = unit;
    }
}
