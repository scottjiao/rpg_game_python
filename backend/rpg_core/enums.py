from enum import Enum

class ActionCategory(str, Enum):
    """第一步：行为大类"""
    ATTACK = "ATTACK"   # 攻击（含普攻和物理技能）
    MAGIC = "MAGIC"     # 法术
    DEFEND = "DEFEND"   # 防御
    ITEM = "ITEM"       # 物品
    FLEE = "FLEE"       # 逃跑


class SkillCategory(str, Enum):
    """技能所属大类，用于菜单分类"""
    ATTACK = "ATTACK"   # 攻击类技能（物理）
    MAGIC = "MAGIC"     # 法术类技能
    SPECIAL = "SPECIAL" # 特殊技能（不归入前两类）

class TargetType(str, Enum):
    SELF = "SELF"
    SINGLE_ENEMY = "SINGLE_ENEMY"
    ALL_ENEMIES = "ALL_ENEMIES"
    SINGLE_ALLY = "SINGLE_ALLY"
    ALL_ALLIES = "ALL_ALLIES"

class DamageType(str, Enum):
    PHYSICAL = "PHYSICAL"
    MAGICAL = "MAGICAL"
    MENTAL = "MENTAL" # 对应 SAN 值伤害
    TRUE = "TRUE"     # 真实伤害
    HEAL = "HEAL"     # 治疗

class EventType(str, Enum):
    BATTLE_START = "BATTLE_START"
    TURN_START = "TURN_START"
    TURN_END = "TURN_END"
    ACTION_CHOSEN = "ACTION_CHOSEN" # 决策层已选好，准备执行
    DAMAGE_DEALT = "DAMAGE_DEALT"   # 伤害已造成
    HEAL_DEALT = "HEAL_DEALT"       # 治疗已造成
    UNIT_DEATH = "UNIT_DEATH"       # 单位死亡
    BATTLE_END = "BATTLE_END"
    LOG = "LOG"                     # 通用日志