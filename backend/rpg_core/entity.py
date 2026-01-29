"""
entity.py - ECS 实体容器

Entity 只是一个组件的容器，不包含任何业务逻辑。
所有的行为都由 System 来处理。
"""
import uuid
from typing import Dict, Type, TypeVar, Optional, List
from pydantic import BaseModel, Field

from .components import (
    Component,
    IdentityComponent,
    StatsComponent,
    ResourceComponent,
    CombatStateComponent,
    SkillsComponent,
    EffectsComponent,
    TeamComponent,
)


T = TypeVar("T", bound=Component)


class Entity(BaseModel):
    """
    ECS 实体：纯粹的组件容器
    
    Entity 本身不包含任何数据或逻辑，只是一个 ID + 组件字典。
    所有业务逻辑都在 System 中实现。
    
    使用方法：
        entity = Entity()
        entity.add(IdentityComponent(name="勇者", template_id="hero"))
        entity.add(StatsComponent(max_hp=100, atk=20))
        
        # 获取组件
        identity = entity.get(IdentityComponent)
        if identity:
            print(identity.name)
        
        # 检查是否有组件
        if entity.has(EffectsComponent):
            ...
    """
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    components: Dict[str, Component] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
    
    def add(self, component: Component) -> "Entity":
        """
        添加组件到实体
        
        如果已存在同类型组件，会被覆盖。
        返回 self 以支持链式调用。
        """
        self.components[component.__class__.__name__] = component
        return self
    
    def get(self, comp_type: Type[T]) -> Optional[T]:
        """
        获取指定类型的组件
        
        Returns:
            组件实例，如果不存在则返回 None
        """
        return self.components.get(comp_type.__name__)
    
    def has(self, comp_type: Type[Component]) -> bool:
        """检查是否拥有指定类型的组件"""
        return comp_type.__name__ in self.components
    
    def remove(self, comp_type: Type[Component]) -> Optional[Component]:
        """
        移除指定类型的组件
        
        Returns:
            被移除的组件，如果不存在则返回 None
        """
        return self.components.pop(comp_type.__name__, None)
    
    def get_all_components(self) -> List[Component]:
        """获取所有组件列表"""
        return list(self.components.values())
    
    # ==================== 便捷属性（语法糖）====================
    # 这些属性让代码更简洁，但底层仍是组件查询
    
    @property
    def name(self) -> str:
        """便捷属性：获取实体名称"""
        identity = self.get(IdentityComponent)
        return identity.name if identity else "Unknown"
    
    @property
    def template_id(self) -> str:
        """便捷属性：获取模板ID"""
        identity = self.get(IdentityComponent)
        return identity.template_id if identity else ""
    
    @property
    def is_dead(self) -> bool:
        """便捷属性：检查是否死亡"""
        state = self.get(CombatStateComponent)
        return state.is_dead if state else False
    
    @is_dead.setter
    def is_dead(self, value: bool):
        """便捷属性：设置死亡状态"""
        state = self.get(CombatStateComponent)
        if state:
            state.is_dead = value
    
    @property
    def team(self) -> str:
        """便捷属性：获取阵营"""
        team_comp = self.get(TeamComponent)
        return team_comp.team if team_comp else ""


class EntityFactory:
    """
    实体工厂：根据模板创建实体
    
    将模板数据转换为带有完整组件的实体。
    """
    
    @staticmethod
    def create_combat_entity(
        name: str,
        template_id: str,
        stats: StatsComponent,
        skill_ids: List[str] = None,
        team: str = "ally"
    ) -> Entity:
        """
        创建战斗实体
        
        Args:
            name: 实体名称
            template_id: 模板 ID
            stats: 基础属性
            skill_ids: 技能 ID 列表
            team: 阵营 ("ally" 或 "enemy")
        
        Returns:
            配置好所有组件的实体
        """
        entity = Entity()
        
        # 身份组件
        entity.add(IdentityComponent(name=name, template_id=template_id))
        
        # 属性组件（存储基础值）
        entity.add(stats)
        
        # 资源组件（初始化为满值）
        entity.add(ResourceComponent(
            current_hp=stats.max_hp,
            current_mp=stats.max_mp,
            current_san=stats.max_san
        ))
        
        # 战斗状态组件
        entity.add(CombatStateComponent())
        
        # 技能组件
        entity.add(SkillsComponent(known_skill_ids=skill_ids or []))
        
        # 效果组件
        entity.add(EffectsComponent())
        
        # 阵营组件
        entity.add(TeamComponent(team=team))
        
        return entity


# ==================== 兼容层：CombatEntity ====================
# 为了向后兼容，提供一个 CombatEntity 别名和兼容方法

class CombatEntity(Entity):
    """
    CombatEntity - 向后兼容的战斗实体
    
    继承自 Entity，添加一些便捷属性以兼容旧代码。
    新代码应该直接使用 Entity + 组件查询。
    """
    
    # ==================== 向后兼容的属性 ====================
    
    @property
    def instance_id(self) -> str:
        """兼容旧代码"""
        return self.id
    
    @property
    def current_hp(self) -> int:
        res = self.get(ResourceComponent)
        return res.current_hp if res else 0
    
    @current_hp.setter
    def current_hp(self, value: int):
        res = self.get(ResourceComponent)
        if res:
            res.current_hp = value
    
    @property
    def current_mp(self) -> int:
        res = self.get(ResourceComponent)
        return res.current_mp if res else 0
    
    @current_mp.setter
    def current_mp(self, value: int):
        res = self.get(ResourceComponent)
        if res:
            res.current_mp = value
    
    @property
    def current_san(self) -> int:
        res = self.get(ResourceComponent)
        return res.current_san if res else 0
    
    @current_san.setter
    def current_san(self, value: int):
        res = self.get(ResourceComponent)
        if res:
            res.current_san = value
    
    @property
    def stats(self) -> Optional[StatsComponent]:
        """兼容旧代码：获取基础属性组件"""
        return self.get(StatsComponent)
    
    @property
    def known_skill_ids(self) -> List[str]:
        skills = self.get(SkillsComponent)
        return skills.known_skill_ids if skills else []
    
    @property
    def cooldowns(self) -> Dict[str, int]:
        skills = self.get(SkillsComponent)
        return skills.cooldowns if skills else {}
    
    @classmethod
    def create(cls, template) -> "CombatEntity":
        """
        兼容旧代码：从 CharacterTemplate 创建实体
        """
        entity = cls()
        
        # 身份组件
        entity.add(IdentityComponent(name=template.name, template_id=template.id))
        
        # 属性组件 - 从 BattleStats 转换为 StatsComponent
        stats = StatsComponent(
            max_hp=template.base_stats.max_hp,
            max_mp=template.base_stats.max_mp,
            max_san=template.base_stats.max_san,
            atk=template.base_stats.atk,
            matk=template.base_stats.matk,
            def_=template.base_stats.def_,
            mdef=template.base_stats.mdef,
            spd=template.base_stats.spd,
            acc=template.base_stats.acc,
            eva=template.base_stats.eva,
            crit=template.base_stats.crit,
            anticrit=template.base_stats.anticrit,
        )
        entity.add(stats)
        
        # 资源组件
        entity.add(ResourceComponent(
            current_hp=template.base_stats.max_hp,
            current_mp=template.base_stats.max_mp,
            current_san=template.base_stats.max_san
        ))
        
        # 战斗状态组件
        entity.add(CombatStateComponent())
        
        # 技能组件
        entity.add(SkillsComponent(known_skill_ids=template.skill_ids or []))
        
        # 效果组件
        entity.add(EffectsComponent())
        
        return entity
