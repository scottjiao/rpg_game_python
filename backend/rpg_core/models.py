"""
models.py - 数据模型定义

包含：
- BattleStats: 战斗属性（兼容层，映射到 StatsComponent）
- SkillTemplate: 技能模板
- CharacterTemplate: 角色模板
- CombatEntity: 战斗实体（ECS 重构版，从 entity.py 导入）
- BattleContext: 战斗上下文
- CombatAction: 战斗行动指令
"""
import uuid
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from .enums import ActionCategory, TargetType, DamageType, SkillCategory

# 导入 ECS 组件和实体
from .entity import CombatEntity  # 重新导出，保持向后兼容
from .components import StatsComponent

# --- 1. 核心属性 Stats ---

class BattleStats(BaseModel):
    """
    战斗属性集。支持通过 + 运算符进行叠加。
    
    注意：这是一个兼容层，用于模板定义。
    实际运行时，属性存储在 StatsComponent 中。
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

    class Config:
        populate_by_name = True

    def __add__(self, other: "BattleStats") -> "BattleStats":
        if not isinstance(other, BattleStats):
            return NotImplemented
        data = {}
        for field in self.model_fields:
            v1 = getattr(self, field)
            v2 = getattr(other, field)
            data[field] = v1 + v2
        return BattleStats(**data)
    
    def to_stats_component(self) -> StatsComponent:
        """转换为 ECS StatsComponent"""
        return StatsComponent(
            max_hp=self.max_hp,
            max_mp=self.max_mp,
            max_san=self.max_san,
            atk=self.atk,
            matk=self.matk,
            def_=self.def_,
            mdef=self.mdef,
            spd=self.spd,
            acc=self.acc,
            eva=self.eva,
            crit=self.crit,
            anticrit=self.anticrit,
        )


# --- 2. 静态模板 Templates (JSON映射) ---

class SkillTemplate(BaseModel):
    """技能/法术模板"""
    id: str
    name: str
    description: str = ""
    category: SkillCategory = SkillCategory.ATTACK  # 技能所属大类：攻击/法术/特殊
    cost_mp: int = 0
    cost_san: int = 0
    cooldown: int = 0
    target_type: TargetType
    damage_type: DamageType
    power_coef: float = 1.0   # 威力系数
    fixed_value: int = 0      # 固定基础值


class CharacterTemplate(BaseModel):
    """角色模板：用于创建 CombatEntity"""
    id: str
    name: str
    base_stats: BattleStats
    skill_ids: List[str] = []


# --- 3. 运行时实体 Runtime Entities ---
# CombatEntity 现在从 entity.py 导入（ECS 架构）
# 这里保留类型引用以保持向后兼容


class BattleContext(BaseModel):
    """战场快照，提供给 Controller 做决策"""
    turn_number: int
    current_actor: CombatEntity
    allies: List[CombatEntity]
    enemies: List[CombatEntity]

    def get_entity(self, eid: str) -> Optional[CombatEntity]:
        for e in self.allies + self.enemies:
            if e.instance_id == eid:
                return e
        return None

    def get_alive_enemies(self) -> List[CombatEntity]:
        return [e for e in self.enemies if not e.is_dead]

    def get_alive_allies(self) -> List[CombatEntity]:
        return [e for e in self.allies if not e.is_dead]


class CombatAction(BaseModel):
    """
    行动指令（三步走的最终产物）:
    1. category   - 行为大类（攻击/法术/防御/物品/逃跑）
    2. skill_id   - 具体技能ID（普攻为 None）
    3. target_ids - 目标列表（群体技能包含多个）
    """
    source_id: str
    category: ActionCategory
    skill_id: Optional[str] = None
    target_ids: List[str] = []
