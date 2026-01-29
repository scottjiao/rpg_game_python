"""
systems.py - ECS 系统

System 负责处理游戏逻辑，操作 Entity 和 Component。
每个 System 都是无状态的，只包含静态方法或工具函数。

核心原则：
- Entity 是数据容器，不包含逻辑
- System 是逻辑容器，不包含数据
- 所有业务逻辑都在 System 中实现
"""
from typing import List, Dict, TYPE_CHECKING

from .components import (
    ResourceComponent,
    StatsComponent,
    EffectsComponent,
    CombatStateComponent,
    SkillsComponent,
)
from .queries import StatQuery, EffectQuery
from .events import EventBus, LogEvent

if TYPE_CHECKING:
    from .entity import Entity
    from .effects import Effect


class EffectSystem:
    """
    效果系统：管理实体身上的 Buff/Debuff
    
    负责：
    - 添加/移除效果
    - 触发效果的时机回调
    - 清理过期效果
    """
    
    @staticmethod
    def add_effect(entity: "Entity", effect: "Effect", bus: EventBus = None):
        """
        为实体添加效果
        
        Args:
            entity: 目标实体
            effect: 要添加的效果
            bus: 事件总线（用于发布日志）
        """
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            effects_comp = EffectsComponent()
            entity.add(effects_comp)
        
        # 检查是否可叠加
        if effect.stackable:
            # 查找同类型效果
            existing = None
            for e in effects_comp.effects:
                if type(e) == type(effect):
                    existing = e
                    break
            
            if existing and existing.current_stacks < existing.max_stacks:
                existing.current_stacks += 1
                existing.duration = max(existing.duration, effect.duration)  # 刷新持续时间
                if bus:
                    bus.publish(LogEvent(
                        message=f"{entity.name} 的 {effect.name} 叠加到 {existing.current_stacks} 层"
                    ))
                return
        
        # 检查同名效果（非叠加型则刷新）
        for i, e in enumerate(effects_comp.effects):
            if e.name == effect.name and not e.stackable:
                effects_comp.effects[i] = effect  # 替换（刷新）
                if bus:
                    bus.publish(LogEvent(message=f"{entity.name} 的 {effect.name} 效果已刷新"))
                return
        
        # 添加新效果
        effects_comp.effects.append(effect)
        if bus:
            bus.publish(LogEvent(message=f"{entity.name} 获得了 {effect.name} 效果"))
    
    @staticmethod
    def remove_effect(entity: "Entity", effect_name: str, bus: EventBus = None):
        """
        移除指定名称的效果
        """
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return
        
        for i, e in enumerate(effects_comp.effects):
            if e.name == effect_name:
                effects_comp.effects.pop(i)
                if bus:
                    bus.publish(LogEvent(message=f"{entity.name} 的 {effect_name} 效果消失了"))
                return
    
    @staticmethod
    def remove_effect_type(entity: "Entity", effect_type: type, bus: EventBus = None):
        """
        移除指定类型的效果
        """
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return
        
        removed = []
        effects_comp.effects = [
            e for e in effects_comp.effects
            if not isinstance(e, effect_type) or removed.append(e)
        ]
        
        if bus:
            for e in removed:
                bus.publish(LogEvent(message=f"{entity.name} 的 {e.name} 效果消失了"))
    
    @staticmethod
    def clear_all_effects(entity: "Entity", buffs_only: bool = False, debuffs_only: bool = False):
        """
        清除所有效果
        
        Args:
            buffs_only: 只清除增益效果
            debuffs_only: 只清除减益效果
        """
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return
        
        if buffs_only:
            effects_comp.effects = [e for e in effects_comp.effects if not e.is_buff]
        elif debuffs_only:
            effects_comp.effects = [e for e in effects_comp.effects if e.is_buff]
        else:
            effects_comp.effects = []
    
    @staticmethod
    def tick_effects(entity: "Entity", trigger: str, context: dict):
        """
        触发效果的时机回调并清理过期效果
        
        Args:
            entity: 目标实体
            trigger: 触发时机 ("TURN_START", "TURN_END" 等)
            context: 战斗上下文
        """
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return
        
        bus = context.get("bus")
        
        # 触发回调
        for effect in effects_comp.effects:
            if trigger == "TURN_START":
                effect.on_turn_start(entity, context)
            elif trigger == "TURN_END":
                effect.on_turn_end(entity, context)
        
        # 减少持续时间
        for effect in effects_comp.effects:
            effect.tick()
        
        # 清理过期效果
        expired = [e for e in effects_comp.effects if e.is_expired()]
        effects_comp.effects = [e for e in effects_comp.effects if not e.is_expired()]
        
        # 发布过期日志
        if bus:
            for e in expired:
                bus.publish(LogEvent(message=f"{entity.name} 的 {e.name} 效果消失了"))


class ResourceSystem:
    """
    资源系统：管理 HP、MP、SAN 的变化
    """
    
    @staticmethod
    def deal_damage(entity: "Entity", amount: int, bus: EventBus = None) -> int:
        """
        对实体造成伤害
        
        会自动应用受伤修正（如无敌效果）
        
        Args:
            entity: 目标实体
            amount: 原始伤害值
            bus: 事件总线
        
        Returns:
            实际造成的伤害
        """
        res = entity.get(ResourceComponent)
        if not res:
            return 0
        
        # 应用受伤修正
        modifier = StatQuery.get_damage_received_modifier(entity)
        actual_damage = int(amount * modifier)
        
        # 如果是无敌状态
        if actual_damage == 0 and amount > 0:
            if bus:
                bus.publish(LogEvent(message=f"{entity.name} 处于无敌状态，免疫了伤害！"))
            return 0
        
        # 扣血
        old_hp = res.current_hp
        res.current_hp = max(0, res.current_hp - actual_damage)
        
        # 检查死亡
        if res.current_hp == 0:
            state = entity.get(CombatStateComponent)
            if state:
                state.is_dead = True
        
        return actual_damage
    
    @staticmethod
    def heal(entity: "Entity", amount: int, bus: EventBus = None) -> int:
        """
        治疗实体
        
        Args:
            entity: 目标实体
            amount: 治疗量
            bus: 事件总线
        
        Returns:
            实际治疗量
        """
        res = entity.get(ResourceComponent)
        stats = entity.get(StatsComponent)
        if not res or not stats:
            return 0
        
        old_hp = res.current_hp
        res.current_hp = min(stats.max_hp, res.current_hp + amount)
        actual_heal = res.current_hp - old_hp
        
        return actual_heal
    
    @staticmethod
    def consume_mp(entity: "Entity", amount: int) -> bool:
        """
        消耗 MP
        
        Args:
            entity: 目标实体
            amount: 消耗量
        
        Returns:
            是否成功消耗（MP 足够）
        """
        res = entity.get(ResourceComponent)
        if not res:
            return False
        
        if res.current_mp < amount:
            return False
        
        res.current_mp -= amount
        return True
    
    @staticmethod
    def restore_mp(entity: "Entity", amount: int) -> int:
        """
        恢复 MP
        
        Returns:
            实际恢复量
        """
        res = entity.get(ResourceComponent)
        stats = entity.get(StatsComponent)
        if not res or not stats:
            return 0
        
        old_mp = res.current_mp
        res.current_mp = min(stats.max_mp, res.current_mp + amount)
        return res.current_mp - old_mp
    
    @staticmethod
    def consume_san(entity: "Entity", amount: int) -> bool:
        """消耗 SAN"""
        res = entity.get(ResourceComponent)
        if not res:
            return False
        
        if res.current_san < amount:
            return False
        
        res.current_san -= amount
        return True


class CooldownSystem:
    """
    冷却系统：管理技能冷却
    """
    
    @staticmethod
    def tick_cooldowns(entity: "Entity"):
        """
        减少所有技能的冷却时间
        """
        skills = entity.get(SkillsComponent)
        if not skills:
            return
        
        for skill_id in list(skills.cooldowns.keys()):
            if skills.cooldowns[skill_id] > 0:
                skills.cooldowns[skill_id] -= 1
                if skills.cooldowns[skill_id] == 0:
                    del skills.cooldowns[skill_id]
    
    @staticmethod
    def set_cooldown(entity: "Entity", skill_id: str, turns: int):
        """
        设置技能冷却
        """
        skills = entity.get(SkillsComponent)
        if not skills:
            return
        
        skills.cooldowns[skill_id] = turns
    
    @staticmethod
    def get_cooldown(entity: "Entity", skill_id: str) -> int:
        """
        获取技能剩余冷却
        """
        skills = entity.get(SkillsComponent)
        if not skills:
            return 0
        
        return skills.cooldowns.get(skill_id, 0)
    
    @staticmethod
    def is_on_cooldown(entity: "Entity", skill_id: str) -> bool:
        """
        检查技能是否在冷却中
        """
        return CooldownSystem.get_cooldown(entity, skill_id) > 0


class DeathSystem:
    """
    死亡系统：处理实体死亡相关逻辑
    """
    
    @staticmethod
    def check_death(entity: "Entity") -> bool:
        """
        检查实体是否应该死亡
        
        Returns:
            True 如果实体刚刚死亡
        """
        res = entity.get(ResourceComponent)
        state = entity.get(CombatStateComponent)
        
        if not res or not state:
            return False
        
        if res.current_hp <= 0 and not state.is_dead:
            state.is_dead = True
            return True
        
        return False
    
    @staticmethod
    def revive(entity: "Entity", hp_percent: float = 0.5, bus: EventBus = None):
        """
        复活实体
        
        Args:
            entity: 目标实体
            hp_percent: 复活后的 HP 百分比
            bus: 事件总线
        """
        res = entity.get(ResourceComponent)
        stats = entity.get(StatsComponent)
        state = entity.get(CombatStateComponent)
        
        if not res or not stats or not state:
            return
        
        if not state.is_dead:
            return
        
        state.is_dead = False
        res.current_hp = int(stats.max_hp * hp_percent)
        
        if bus:
            bus.publish(LogEvent(message=f"{entity.name} 复活了！"))
