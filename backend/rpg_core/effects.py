"""
effects.py - 效果/Buff 系统

Effect 是附加到实体上的临时效果，可以：
1. 在特定时机触发（回合开始、回合结束、受到伤害时等）
2. 修正属性值（攻击力+50%、防御力-20等）
3. 添加/移除标签组件

这是 ECS 架构中"组合优于继承"的核心体现：
- 不需要为每种状态创建子类
- 通过组合多个 Effect 实现复杂效果
- 易于序列化和网络传输
"""
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from .entity import Entity


class EffectTrigger(str, Enum):
    """效果触发时机"""
    TURN_START = "TURN_START"          # 回合开始时
    TURN_END = "TURN_END"              # 回合结束时
    BEFORE_ATTACK = "BEFORE_ATTACK"    # 攻击前
    AFTER_ATTACK = "AFTER_ATTACK"      # 攻击后
    BEFORE_DAMAGE = "BEFORE_DAMAGE"    # 受到伤害前
    AFTER_DAMAGE = "AFTER_DAMAGE"      # 受到伤害后
    ON_DEATH = "ON_DEATH"              # 死亡时


class Effect(ABC):
    """
    效果基类
    
    所有 Buff/Debuff 都继承此类。
    Effect 可以：
    1. 有持续时间（duration）
    2. 在特定时机触发 (on_turn_start, on_turn_end 等)
    3. 修正属性值 (modify_stat)
    """
    
    def __init__(
        self,
        duration: int = -1,
        source_id: Optional[str] = None,
        name: str = "未命名效果",
        description: str = "",
        is_buff: bool = True,
        stackable: bool = False,
        max_stacks: int = 1,
    ):
        """
        Args:
            duration: 持续回合数，-1 表示永久
            source_id: 施加此效果的实体 ID
            name: 效果名称（用于 UI 显示）
            description: 效果描述
            is_buff: True 为增益，False 为减益
            stackable: 是否可叠加
            max_stacks: 最大叠加层数
        """
        self.duration = duration
        self.source_id = source_id
        self.name = name
        self.description = description
        self.is_buff = is_buff
        self.stackable = stackable
        self.max_stacks = max_stacks
        self.current_stacks = 1
    
    def tick(self):
        """每回合调用，减少持续时间"""
        if self.duration > 0:
            self.duration -= 1
    
    def is_expired(self) -> bool:
        """检查效果是否已过期"""
        return self.duration == 0
    
    # ==================== 触发钩子 ====================
    
    def on_turn_start(self, entity: "Entity", context: dict):
        """
        回合开始时触发
        
        Args:
            entity: 拥有此效果的实体
            context: 战斗上下文（包含事件总线等）
        """
        pass
    
    def on_turn_end(self, entity: "Entity", context: dict):
        """回合结束时触发"""
        pass
    
    def on_before_attack(self, entity: "Entity", target: "Entity", context: dict):
        """攻击前触发"""
        pass
    
    def on_after_attack(self, entity: "Entity", target: "Entity", damage: int, context: dict):
        """攻击后触发"""
        pass
    
    def on_before_damage(self, entity: "Entity", damage: int, source: "Entity", context: dict) -> int:
        """
        受到伤害前触发
        
        Returns:
            修正后的伤害值
        """
        return damage
    
    def on_after_damage(self, entity: "Entity", damage: int, source: "Entity", context: dict):
        """受到伤害后触发"""
        pass
    
    def on_death(self, entity: "Entity", context: dict):
        """死亡时触发"""
        pass
    
    # ==================== 属性修正钩子 ====================
    
    def modify_stat(self, stat_name: str, base_value: float) -> float:
        """
        修正属性值
        
        这是实现属性增减的核心方法。
        例如：狂暴效果让攻击力 +50%
        
        Args:
            stat_name: 属性名 ("atk", "def_", "spd" 等)
            base_value: 当前属性值（可能已被其他效果修正过）
        
        Returns:
            修正后的属性值
        """
        return base_value
    
    def modify_damage_dealt(self, damage: float) -> float:
        """
        修正造成的伤害
        
        Returns:
            修正后的伤害值
        """
        return damage
    
    def modify_damage_received(self, damage: float) -> float:
        """
        修正受到的伤害
        
        Returns:
            修正后的伤害值
        """
        return damage


# ============================================================
# 具体效果实现
# ============================================================

class PoisonEffect(Effect):
    """
    中毒效果：每回合开始时造成固定伤害
    """
    
    def __init__(self, duration: int = 3, damage_per_turn: int = 10, source_id: str = None):
        super().__init__(
            duration=duration,
            source_id=source_id,
            name="中毒",
            description=f"每回合受到 {damage_per_turn} 点伤害",
            is_buff=False,
        )
        self.damage_per_turn = damage_per_turn
    
    def on_turn_start(self, entity: "Entity", context: dict):
        from .components import ResourceComponent
        from .events import LogEvent
        
        res = entity.get(ResourceComponent)
        if res:
            res.current_hp = max(0, res.current_hp - self.damage_per_turn)
            
            # 发布日志事件
            bus = context.get("bus")
            if bus:
                bus.publish(LogEvent(message=f"{entity.name} 受到中毒伤害 -{self.damage_per_turn}"))


class BurnEffect(Effect):
    """
    燃烧效果：每回合开始时造成火焰伤害
    """
    
    def __init__(self, duration: int = 2, damage_per_turn: int = 15, source_id: str = None):
        super().__init__(
            duration=duration,
            source_id=source_id,
            name="燃烧",
            description=f"每回合受到 {damage_per_turn} 点火焰伤害",
            is_buff=False,
        )
        self.damage_per_turn = damage_per_turn
    
    def on_turn_start(self, entity: "Entity", context: dict):
        from .components import ResourceComponent
        from .events import LogEvent
        
        res = entity.get(ResourceComponent)
        if res:
            res.current_hp = max(0, res.current_hp - self.damage_per_turn)
            
            bus = context.get("bus")
            if bus:
                bus.publish(LogEvent(message=f"{entity.name} 受到燃烧伤害 -{self.damage_per_turn}"))


class RageEffect(Effect):
    """
    狂暴效果：攻击力 +50%
    """
    
    def __init__(self, duration: int = 3, atk_bonus: float = 0.5, source_id: str = None):
        super().__init__(
            duration=duration,
            source_id=source_id,
            name="狂暴",
            description=f"攻击力 +{int(atk_bonus * 100)}%",
            is_buff=True,
        )
        self.atk_bonus = atk_bonus
    
    def modify_stat(self, stat_name: str, base_value: float) -> float:
        if stat_name == "atk":
            return base_value * (1 + self.atk_bonus)
        return base_value


class DefenseUpEffect(Effect):
    """
    防御强化效果：防御力提升
    """
    
    def __init__(self, duration: int = 2, def_bonus: float = 0.3, source_id: str = None):
        super().__init__(
            duration=duration,
            source_id=source_id,
            name="防御强化",
            description=f"防御力 +{int(def_bonus * 100)}%",
            is_buff=True,
        )
        self.def_bonus = def_bonus
    
    def modify_stat(self, stat_name: str, base_value: float) -> float:
        if stat_name == "def_":
            return base_value * (1 + self.def_bonus)
        return base_value


class WeakenEffect(Effect):
    """
    虚弱效果：攻击力 -30%
    """
    
    def __init__(self, duration: int = 2, atk_penalty: float = 0.3, source_id: str = None):
        super().__init__(
            duration=duration,
            source_id=source_id,
            name="虚弱",
            description=f"攻击力 -{int(atk_penalty * 100)}%",
            is_buff=False,
        )
        self.atk_penalty = atk_penalty
    
    def modify_stat(self, stat_name: str, base_value: float) -> float:
        if stat_name == "atk":
            return base_value * (1 - self.atk_penalty)
        return base_value


class InvincibleEffect(Effect):
    """
    无敌效果：免疫所有伤害
    """
    
    def __init__(self, duration: int = 1, source_id: str = None):
        super().__init__(
            duration=duration,
            source_id=source_id,
            name="无敌",
            description="免疫所有伤害",
            is_buff=True,
        )
    
    def modify_damage_received(self, damage: float) -> float:
        return 0


class RegenEffect(Effect):
    """
    再生效果：每回合恢复 HP
    """
    
    def __init__(self, duration: int = 3, heal_per_turn: int = 15, source_id: str = None):
        super().__init__(
            duration=duration,
            source_id=source_id,
            name="再生",
            description=f"每回合恢复 {heal_per_turn} HP",
            is_buff=True,
        )
        self.heal_per_turn = heal_per_turn
    
    def on_turn_start(self, entity: "Entity", context: dict):
        from .components import ResourceComponent, StatsComponent
        from .events import LogEvent
        
        res = entity.get(ResourceComponent)
        stats = entity.get(StatsComponent)
        if res and stats:
            old_hp = res.current_hp
            res.current_hp = min(stats.max_hp, res.current_hp + self.heal_per_turn)
            actual_heal = res.current_hp - old_hp
            
            if actual_heal > 0:
                bus = context.get("bus")
                if bus:
                    bus.publish(LogEvent(message=f"{entity.name} 再生恢复 +{actual_heal} HP"))


class StunEffect(Effect):
    """
    眩晕效果：无法行动
    """
    
    def __init__(self, duration: int = 1, source_id: str = None):
        super().__init__(
            duration=duration,
            source_id=source_id,
            name="眩晕",
            description="无法行动",
            is_buff=False,
        )
        self.skip_turn = True  # 标记需要跳过回合


class SilenceEffect(Effect):
    """
    沉默效果：无法使用法术
    """
    
    def __init__(self, duration: int = 2, source_id: str = None):
        super().__init__(
            duration=duration,
            source_id=source_id,
            name="沉默",
            description="无法使用法术",
            is_buff=False,
        )
        self.block_magic = True  # 标记禁用法术
