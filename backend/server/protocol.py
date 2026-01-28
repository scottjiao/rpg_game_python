"""
protocol.py - 前后端通信协议定义

定义所有 WebSocket 消息的格式，确保前后端解耦。
"""
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


# ==================== 消息类型 ====================

class ServerMsgType(str, Enum):
    """服务器 -> 客户端 的消息类型"""
    # 初始化
    INIT_STATE = "INIT_STATE"           # 战斗开始时发送完整状态
    
    # 状态更新
    UPDATE_HP = "UPDATE_HP"             # HP 变化
    UPDATE_MP = "UPDATE_MP"             # MP 变化
    UNIT_DIED = "UNIT_DIED"             # 单位死亡
    
    # 事件通知
    LOG = "LOG"                         # 日志消息
    TURN_START = "TURN_START"           # 回合开始
    DAMAGE = "DAMAGE"                   # 伤害事件
    HEAL = "HEAL"                       # 治疗事件
    BATTLE_END = "BATTLE_END"           # 战斗结束
    
    # 请求玩家操作
    REQUEST_ACTION = "REQUEST_ACTION"   # 请求玩家选择动作
    REQUEST_SKILL = "REQUEST_SKILL"     # 请求玩家选择技能
    REQUEST_TARGET = "REQUEST_TARGET"   # 请求玩家选择目标


class ClientMsgType(str, Enum):
    """客户端 -> 服务器 的消息类型"""
    START_BATTLE = "START_BATTLE"       # 开始战斗
    SELECT_CATEGORY = "SELECT_CATEGORY" # 选择行动类型
    SELECT_SKILL = "SELECT_SKILL"       # 选择技能
    SELECT_TARGET = "SELECT_TARGET"     # 选择目标
    RESTART = "RESTART"                 # 重新开始


# ==================== 数据结构 ====================

class UnitInfo(BaseModel):
    """单位信息（用于初始化和状态展示）"""
    id: str
    name: str
    current_hp: int
    max_hp: int
    current_mp: int
    max_mp: int
    is_dead: bool = False
    team: str  # "ally" or "enemy"


class SkillInfo(BaseModel):
    """技能信息"""
    id: str
    name: str
    cost_mp: int = 0
    cost_san: int = 0
    cooldown: int = 0
    current_cd: int = 0
    description: str = ""
    is_usable: bool = True       # 新增字段：总的是否可用
    unusable_reason: str = ""    # 新增字段：不可用原因（CD中/MP不足...）


class CategoryOption(BaseModel):
    """行动类型选项"""
    id: str       # ActionCategory 的值
    name: str     # 显示名称


class TargetOption(BaseModel):
    """目标选项"""
    id: str
    name: str
    current_hp: int
    max_hp: int


# ==================== 服务端消息 ====================

class ServerMessage(BaseModel):
    """服务端消息基类"""
    type: ServerMsgType
    data: Dict[str, Any] = {}


class InitStateData(BaseModel):
    """初始化状态数据"""
    allies: List[UnitInfo]
    enemies: List[UnitInfo]
    turn_number: int = 0


class RequestActionData(BaseModel):
    """请求行动选择的数据"""
    actor_id: str
    actor_name: str
    categories: List[CategoryOption]


class RequestSkillData(BaseModel):
    """请求技能选择的数据"""
    actor_id: str
    category: str
    category_name: str
    has_basic_attack: bool  # 是否有普攻选项
    skills: List[SkillInfo]


class RequestTargetData(BaseModel):
    """请求目标选择的数据"""
    actor_id: str
    skill_id: Optional[str]  # None 表示普攻
    skill_name: str
    is_aoe: bool
    targets: List[TargetOption]


class DamageData(BaseModel):
    """伤害事件数据"""
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    amount: int
    is_crit: bool
    damage_type: str
    remaining_hp: int
    max_hp: int


class HealData(BaseModel):
    """治疗事件数据"""
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    amount: int
    remaining_hp: int
    max_hp: int


class TurnStartData(BaseModel):
    """回合开始数据"""
    turn_number: int
    actor_id: str
    actor_name: str


class BattleEndData(BaseModel):
    """战斗结束数据"""
    winner: str  # "allies" or "enemies"
    message: str


# ==================== 客户端消息 ====================

class ClientMessage(BaseModel):
    """客户端消息"""
    type: ClientMsgType
    data: Dict[str, Any] = {}
