"""
components.py - ECS 组件定义

所有组件都是纯数据容器，不包含任何业务逻辑。
组件可以动态地附加到实体上，实现"组合优于继承"的设计。
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class Component(BaseModel):
    """组件基类 - 所有组件继承此类"""
    
    class Config:
        # 允许通过别名访问字段
        populate_by_name = True


# ============================================================
# 身份与元信息组件
# ============================================================

class IdentityComponent(Component):
    """身份信息组件：名称、模板引用等"""
    name: str
    template_id: str


# ============================================================
# 属性组件 (Stats)
# ============================================================

class StatsComponent(Component):
    """
    基础属性组件：角色的固有属性值（基础值）
    这些值不会被 Buff 直接修改，Buff 的修正在查询时动态计算
    """
    # 资源上限
    max_hp: int = 0
    max_mp: int = 0
    max_san: int = 0
    
    # 攻防属性
    atk: int = 0
    matk: int = 0
    def_: int = Field(0, alias="def")
    mdef: int = 0
    
    # 速度与命中
    spd: int = 0
    acc: float = 0.0
    eva: float = 0.0
    
    # 暴击
    crit: float = 0.0
    anticrit: float = 0.0

    def __add__(self, other: "StatsComponent") -> "StatsComponent":
        """支持属性叠加"""
        if not isinstance(other, StatsComponent):
            return NotImplemented
        data = {}
        for field in self.model_fields:
            v1 = getattr(self, field)
            v2 = getattr(other, field)
            data[field] = v1 + v2
        return StatsComponent(**data)


class ResourceComponent(Component):
    """
    动态资源组件：HP、MP、SAN 等会在战斗中变化的值
    与 StatsComponent 分离，便于独立更新和序列化
    """
    current_hp: int = 0
    current_mp: int = 0
    current_san: int = 0


class CombatStateComponent(Component):
    """
    战斗状态组件：死亡、防御姿态等战斗相关的布尔状态
    """
    is_dead: bool = False
    is_defending: bool = False  # 防御姿态（减伤）


# ============================================================
# 技能与冷却组件
# ============================================================

class SkillsComponent(Component):
    """
    技能组件：角色拥有的技能列表和冷却状态
    """
    known_skill_ids: List[str] = []
    cooldowns: Dict[str, int] = {}  # skill_id -> turns_remaining


# ============================================================
# 效果/Buff 组件
# ============================================================

class EffectsComponent(Component):
    """
    效果容器组件：存储当前生效的所有 Buff/Debuff
    实际的 Effect 对象存储在这里，由 EffectSystem 处理
    """
    effects: List[Any] = []  # List[Effect]，使用 Any 避免循环导入


# ============================================================
# 标签组件 (Tag Components) - 用于快速判断状态
# ============================================================

class InvincibleTagComponent(Component):
    """无敌标签：拥有此组件的实体不会受到伤害"""
    pass


class SilencedTagComponent(Component):
    """沉默标签：拥有此组件的实体无法使用法术"""
    pass


class StunnedTagComponent(Component):
    """眩晕标签：拥有此组件的实体无法行动"""
    pass


class PoisonedTagComponent(Component):
    """中毒标签：回合开始时受到伤害"""
    damage_per_turn: int = 10


class BurningTagComponent(Component):
    """燃烧标签：回合开始时受到火焰伤害"""
    damage_per_turn: int = 15


# ============================================================
# 阵营组件
# ============================================================

class TeamComponent(Component):
    """
    阵营组件：标识实体属于哪个队伍
    """
    team: str  # "ally" 或 "enemy"
