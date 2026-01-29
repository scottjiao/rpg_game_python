"""
rpg_core - RPG 战斗系统核心模块

ECS 架构重构版本：
- Entity: 纯数据容器，不包含逻辑
- Component: 数据组件（属性、资源、效果等）
- System: 逻辑处理器（效果系统、冷却系统等）
- Query: 属性查询服务（自动计算 Buff 修正）

核心模块：
- entity.py: Entity 和 CombatEntity 定义
- components.py: 所有 Component 定义
- effects.py: Effect 基类和具体效果实现
- systems.py: EffectSystem, ResourceSystem 等
- queries.py: StatQuery, EffectQuery 等查询服务

传统模块（兼容层）：
- models.py: 模板定义和向后兼容的 CombatEntity
- enums.py: 枚举类型
- events.py: 事件系统
- logic.py: ActionGenerator, DamageCalculator
- engine.py: BattleEngine
- controllers.py: 控制器
"""

# ECS 核心
from .entity import Entity, CombatEntity, EntityFactory
from .components import (
    Component,
    IdentityComponent,
    StatsComponent,
    ResourceComponent,
    CombatStateComponent,
    SkillsComponent,
    EffectsComponent,
    TeamComponent,
    # Tag Components
    InvincibleTagComponent,
    SilencedTagComponent,
    StunnedTagComponent,
    PoisonedTagComponent,
    BurningTagComponent,
)
from .effects import (
    Effect,
    EffectTrigger,
    PoisonEffect,
    BurnEffect,
    RageEffect,
    DefenseUpEffect,
    WeakenEffect,
    InvincibleEffect,
    RegenEffect,
    StunEffect,
    SilenceEffect,
)
from .systems import (
    EffectSystem,
    ResourceSystem,
    CooldownSystem,
    DeathSystem,
)
from .queries import (
    StatQuery,
    ResourceQuery,
    EffectQuery,
)

# 传统模块
from .enums import (
    ActionCategory,
    SkillCategory,
    TargetType,
    DamageType,
    EventType,
)
from .models import (
    BattleStats,
    SkillTemplate,
    CharacterTemplate,
    BattleContext,
    CombatAction,
)
from .events import (
    EventBus,
    BaseEvent,
    LogEvent,
    TurnEvent,
    DamageEvent,
    BattleEndEvent,
)
from .logic import (
    ActionGenerator,
    DamageCalculator,
)
from .engine import BattleEngine
from .controllers import (
    BaseController,
    RandomAIController,
    HumanCLIController,
)

__all__ = [
    # ECS Core
    "Entity",
    "CombatEntity",
    "EntityFactory",
    # Components
    "Component",
    "IdentityComponent",
    "StatsComponent",
    "ResourceComponent",
    "CombatStateComponent",
    "SkillsComponent",
    "EffectsComponent",
    "TeamComponent",
    "InvincibleTagComponent",
    "SilencedTagComponent",
    "StunnedTagComponent",
    "PoisonedTagComponent",
    "BurningTagComponent",
    # Effects
    "Effect",
    "EffectTrigger",
    "PoisonEffect",
    "BurnEffect",
    "RageEffect",
    "DefenseUpEffect",
    "WeakenEffect",
    "InvincibleEffect",
    "RegenEffect",
    "StunEffect",
    "SilenceEffect",
    # Systems
    "EffectSystem",
    "ResourceSystem",
    "CooldownSystem",
    "DeathSystem",
    # Queries
    "StatQuery",
    "ResourceQuery",
    "EffectQuery",
    # Enums
    "ActionCategory",
    "SkillCategory",
    "TargetType",
    "DamageType",
    "EventType",
    # Models
    "BattleStats",
    "SkillTemplate",
    "CharacterTemplate",
    "BattleContext",
    "CombatAction",
    # Events
    "EventBus",
    "BaseEvent",
    "LogEvent",
    "TurnEvent",
    "DamageEvent",
    "BattleEndEvent",
    # Logic
    "ActionGenerator",
    "DamageCalculator",
    # Engine & Controllers
    "BattleEngine",
    "BaseController",
    "RandomAIController",
    "HumanCLIController",
]
