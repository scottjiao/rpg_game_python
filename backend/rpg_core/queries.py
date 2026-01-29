"""
queries.py - 属性查询服务

提供统一的属性查询 API，自动计算 Buff 修正后的最终属性值。

关键设计：
- 所有属性访问都应通过 StatQuery 进行
- 不要直接读取 entity.get(StatsComponent).atk
- 应该使用 StatQuery.get(entity, "atk")

这样可以确保 Buff 系统的修正被正确应用。
"""
from typing import TYPE_CHECKING, Optional

from .components import StatsComponent, EffectsComponent, ResourceComponent

if TYPE_CHECKING:
    from .entity import Entity


class StatQuery:
    """
    属性查询服务
    
    提供经过所有 Buff/Effect 修正后的最终属性值。
    这是 ECS 架构中"数据查询"的核心入口。
    """
    
    @staticmethod
    def get(entity: "Entity", stat_name: str) -> float:
        """
        获取经过所有 Buff 修正后的最终属性值
        
        Args:
            entity: 要查询的实体
            stat_name: 属性名 ("atk", "def_", "spd", "max_hp" 等)
        
        Returns:
            修正后的最终属性值
        
        Example:
            # 假设勇者基础攻击力 20，有一个 +50% 攻击力的狂暴 Buff
            atk = StatQuery.get(hero, "atk")  # 返回 30
        """
        stats = entity.get(StatsComponent)
        if not stats:
            return 0
        
        # 1. 获取基础值
        base_value = getattr(stats, stat_name, 0)
        
        # 2. 遍历所有 Effect 进行修正
        effects_comp = entity.get(EffectsComponent)
        if effects_comp:
            for effect in effects_comp.effects:
                base_value = effect.modify_stat(stat_name, base_value)
        
        return base_value
    
    @staticmethod
    def get_int(entity: "Entity", stat_name: str) -> int:
        """获取整数属性值"""
        return int(StatQuery.get(entity, stat_name))
    
    @staticmethod
    def get_effective_stats(entity: "Entity") -> dict:
        """
        获取所有经过修正的属性
        
        Returns:
            包含所有属性名和修正后值的字典
        """
        stats = entity.get(StatsComponent)
        if not stats:
            return {}
        
        result = {}
        for field_name in stats.model_fields:
            result[field_name] = StatQuery.get(entity, field_name)
        
        return result
    
    @staticmethod
    def get_damage_dealt_modifier(entity: "Entity") -> float:
        """
        获取造成伤害的修正系数
        
        遍历所有 Effect 的 modify_damage_dealt
        
        Returns:
            伤害修正后的系数（1.0 表示无修正）
        """
        effects_comp = entity.get(EffectsComponent)
        damage = 1.0
        
        if effects_comp:
            for effect in effects_comp.effects:
                damage = effect.modify_damage_dealt(damage)
        
        return damage
    
    @staticmethod
    def get_damage_received_modifier(entity: "Entity") -> float:
        """
        获取受到伤害的修正系数
        
        遍历所有 Effect 的 modify_damage_received
        
        Returns:
            伤害修正后的系数（1.0 表示无修正，0 表示免疫）
        """
        effects_comp = entity.get(EffectsComponent)
        damage = 1.0
        
        if effects_comp:
            for effect in effects_comp.effects:
                damage = effect.modify_damage_received(damage)
        
        return damage


class ResourceQuery:
    """
    资源查询服务
    
    提供当前资源值（HP、MP、SAN）的查询。
    """
    
    @staticmethod
    def get_hp(entity: "Entity") -> int:
        """获取当前 HP"""
        res = entity.get(ResourceComponent)
        return res.current_hp if res else 0
    
    @staticmethod
    def get_mp(entity: "Entity") -> int:
        """获取当前 MP"""
        res = entity.get(ResourceComponent)
        return res.current_mp if res else 0
    
    @staticmethod
    def get_san(entity: "Entity") -> int:
        """获取当前 SAN"""
        res = entity.get(ResourceComponent)
        return res.current_san if res else 0
    
    @staticmethod
    def get_hp_percent(entity: "Entity") -> float:
        """获取 HP 百分比 (0.0 ~ 1.0)"""
        res = entity.get(ResourceComponent)
        stats = entity.get(StatsComponent)
        if not res or not stats or stats.max_hp == 0:
            return 0.0
        return res.current_hp / stats.max_hp
    
    @staticmethod
    def get_mp_percent(entity: "Entity") -> float:
        """获取 MP 百分比 (0.0 ~ 1.0)"""
        res = entity.get(ResourceComponent)
        stats = entity.get(StatsComponent)
        if not res or not stats or stats.max_mp == 0:
            return 0.0
        return res.current_mp / stats.max_mp


class EffectQuery:
    """
    效果查询服务
    
    查询实体身上的 Buff/Debuff 状态。
    """
    
    @staticmethod
    def has_effect(entity: "Entity", effect_name: str) -> bool:
        """检查是否有指定名称的效果"""
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return False
        return any(e.name == effect_name for e in effects_comp.effects)
    
    @staticmethod
    def has_effect_type(entity: "Entity", effect_type: type) -> bool:
        """检查是否有指定类型的效果"""
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return False
        return any(isinstance(e, effect_type) for e in effects_comp.effects)
    
    @staticmethod
    def get_effect(entity: "Entity", effect_name: str):
        """获取指定名称的效果"""
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return None
        for e in effects_comp.effects:
            if e.name == effect_name:
                return e
        return None
    
    @staticmethod
    def get_all_effects(entity: "Entity") -> list:
        """获取所有效果"""
        effects_comp = entity.get(EffectsComponent)
        return effects_comp.effects if effects_comp else []
    
    @staticmethod
    def get_buffs(entity: "Entity") -> list:
        """获取所有增益效果"""
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return []
        return [e for e in effects_comp.effects if e.is_buff]
    
    @staticmethod
    def get_debuffs(entity: "Entity") -> list:
        """获取所有减益效果"""
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return []
        return [e for e in effects_comp.effects if not e.is_buff]
    
    @staticmethod
    def is_stunned(entity: "Entity") -> bool:
        """检查是否被眩晕（无法行动）"""
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return False
        return any(getattr(e, 'skip_turn', False) for e in effects_comp.effects)
    
    @staticmethod
    def is_silenced(entity: "Entity") -> bool:
        """检查是否被沉默（无法使用法术）"""
        effects_comp = entity.get(EffectsComponent)
        if not effects_comp:
            return False
        return any(getattr(e, 'block_magic', False) for e in effects_comp.effects)
