"""
skill_effects.py - 技能效果注册表

将技能的特殊效果（Effect）与数据配置解耦。
技能数据在 JSON 中定义 effect_ids，运行时从这里查找对应的效果逻辑。

设计原则：
- 每个效果是一个独立函数或类，可复用于多个技能
- 效果参数从 JSON 的 effect_params 传入
- 支持组合多个效果（一个技能可以有多个 effect_ids）
"""
from typing import Dict, Any, Callable, TYPE_CHECKING, Optional
from dataclasses import dataclass

from .effects import (
    Effect, PoisonEffect, BurnEffect, RageEffect, 
    DefenseUpEffect, RegenEffect
)

if TYPE_CHECKING:
    from .entity import CombatEntity
    from .events import EventBus


@dataclass
class SkillEffectContext:
    """
    技能效果执行上下文
    
    提供效果执行所需的所有信息
    """
    source: "CombatEntity"          # 施放者
    target: "CombatEntity"          # 目标（单体效果）
    targets: list                    # 目标列表（群体效果）
    damage_dealt: int = 0           # 本次技能造成的伤害
    params: Dict[str, Any] = None   # 效果参数（来自 JSON）
    bus: Optional["EventBus"] = None  # 事件总线
    
    def __post_init__(self):
        if self.params is None:
            self.params = {}
        if self.targets is None:
            self.targets = []


# ============================================================
# 效果注册表
# ============================================================

# 效果处理函数类型：接收上下文，返回 None
EffectHandler = Callable[[SkillEffectContext], None]

# 全局效果注册表
SKILL_EFFECT_REGISTRY: Dict[str, EffectHandler] = {}


def register_skill_effect(effect_id: str):
    """
    装饰器：注册技能效果
    
    用法：
        @register_skill_effect("apply_poison")
        def apply_poison_effect(ctx: SkillEffectContext):
            ...
    """
    def decorator(func: EffectHandler) -> EffectHandler:
        SKILL_EFFECT_REGISTRY[effect_id] = func
        return func
    return decorator


def get_skill_effect(effect_id: str) -> Optional[EffectHandler]:
    """获取技能效果处理函数"""
    return SKILL_EFFECT_REGISTRY.get(effect_id)


def execute_skill_effects(
    effect_ids: list,
    effect_params: Dict[str, Dict[str, Any]],
    ctx: SkillEffectContext
):
    """
    执行技能的所有效果
    
    Args:
        effect_ids: 效果 ID 列表
        effect_params: 效果参数字典 {effect_id: params}
        ctx: 效果执行上下文
    """
    for effect_id in effect_ids:
        handler = get_skill_effect(effect_id)
        if handler:
            # 更新上下文中的参数
            ctx.params = effect_params.get(effect_id, {})
            handler(ctx)
        else:
            print(f"Warning: Unknown skill effect '{effect_id}'")


# ============================================================
# 内置效果实现
# ============================================================

@register_skill_effect("apply_poison")
def apply_poison_effect(ctx: SkillEffectContext):
    """
    施加中毒效果
    
    参数：
        duration: 持续回合数（默认 3）
        damage_per_turn: 每回合伤害（默认 10）
    """
    from .components import EffectsComponent
    
    duration = ctx.params.get("duration", 3)
    damage_per_turn = ctx.params.get("damage_per_turn", 10)
    
    effects_comp = ctx.target.get(EffectsComponent)
    if effects_comp:
        poison = PoisonEffect(
            duration=duration,
            damage_per_turn=damage_per_turn,
            source_id=ctx.source.id
        )
        effects_comp.add_effect(poison)
        
        if ctx.bus:
            from .events import LogEvent
            ctx.bus.publish(LogEvent(
                message=f"{ctx.target.name} 中毒了！（{duration}回合）"
            ))


@register_skill_effect("apply_burn")
def apply_burn_effect(ctx: SkillEffectContext):
    """
    施加燃烧效果
    
    参数：
        duration: 持续回合数（默认 2）
        damage_per_turn: 每回合伤害（默认 15）
    """
    from .components import EffectsComponent
    
    duration = ctx.params.get("duration", 2)
    damage_per_turn = ctx.params.get("damage_per_turn", 15)
    
    # 群体效果：对所有目标施加
    targets = ctx.targets if ctx.targets else [ctx.target]
    
    for target in targets:
        effects_comp = target.get(EffectsComponent)
        if effects_comp:
            burn = BurnEffect(
                duration=duration,
                damage_per_turn=damage_per_turn,
                source_id=ctx.source.id
            )
            effects_comp.add_effect(burn)
            
            if ctx.bus:
                from .events import LogEvent
                ctx.bus.publish(LogEvent(
                    message=f"{target.name} 被点燃了！（{duration}回合）"
                ))


@register_skill_effect("apply_rage")
def apply_rage_effect(ctx: SkillEffectContext):
    """
    施加狂暴效果（自身增益）
    
    参数：
        duration: 持续回合数（默认 3）
        atk_bonus: 攻击力加成比例（默认 0.5 = 50%）
    """
    from .components import EffectsComponent
    
    duration = ctx.params.get("duration", 3)
    atk_bonus = ctx.params.get("atk_bonus", 0.5)
    
    effects_comp = ctx.source.get(EffectsComponent)
    if effects_comp:
        rage = RageEffect(
            duration=duration,
            atk_bonus=atk_bonus,
            source_id=ctx.source.id
        )
        effects_comp.add_effect(rage)
        
        if ctx.bus:
            from .events import LogEvent
            ctx.bus.publish(LogEvent(
                message=f"{ctx.source.name} 进入狂暴状态！攻击力 +{int(atk_bonus * 100)}%"
            ))


@register_skill_effect("apply_defense_up")
def apply_defense_up_effect(ctx: SkillEffectContext):
    """
    施加防御强化效果
    
    参数：
        duration: 持续回合数（默认 2）
        def_bonus: 防御力加成比例（默认 0.3 = 30%）
    """
    from .components import EffectsComponent
    
    duration = ctx.params.get("duration", 2)
    def_bonus = ctx.params.get("def_bonus", 0.3)
    
    effects_comp = ctx.target.get(EffectsComponent)
    if effects_comp:
        defense = DefenseUpEffect(
            duration=duration,
            def_bonus=def_bonus,
            source_id=ctx.source.id
        )
        effects_comp.add_effect(defense)
        
        if ctx.bus:
            from .events import LogEvent
            ctx.bus.publish(LogEvent(
                message=f"{ctx.target.name} 防御力提升！+{int(def_bonus * 100)}%"
            ))


@register_skill_effect("apply_regen")
def apply_regen_effect(ctx: SkillEffectContext):
    """
    施加再生效果
    
    参数：
        duration: 持续回合数（默认 3）
        heal_per_turn: 每回合恢复量（默认 15）
    """
    from .components import EffectsComponent
    
    duration = ctx.params.get("duration", 3)
    heal_per_turn = ctx.params.get("heal_per_turn", 15)
    
    effects_comp = ctx.target.get(EffectsComponent)
    if effects_comp:
        regen = RegenEffect(
            duration=duration,
            heal_per_turn=heal_per_turn,
            source_id=ctx.source.id
        )
        effects_comp.add_effect(regen)
        
        if ctx.bus:
            from .events import LogEvent
            ctx.bus.publish(LogEvent(
                message=f"{ctx.target.name} 获得再生效果！每回合恢复 {heal_per_turn} HP"
            ))


@register_skill_effect("lifesteal")
def lifesteal_effect(ctx: SkillEffectContext):
    """
    吸血效果：根据造成的伤害恢复自身 HP
    
    参数：
        percent: 吸血比例（默认 0.2 = 20%）
    """
    from .components import ResourceComponent, StatsComponent
    
    percent = ctx.params.get("percent", 0.2)
    
    if ctx.damage_dealt <= 0:
        return
    
    heal_amount = int(ctx.damage_dealt * percent)
    
    res = ctx.source.get(ResourceComponent)
    stats = ctx.source.get(StatsComponent)
    
    if res and stats and heal_amount > 0:
        old_hp = res.current_hp
        res.current_hp = min(stats.max_hp, res.current_hp + heal_amount)
        actual_heal = res.current_hp - old_hp
        
        if actual_heal > 0 and ctx.bus:
            from .events import LogEvent
            ctx.bus.publish(LogEvent(
                message=f"{ctx.source.name} 吸取了 {actual_heal} HP！"
            ))
