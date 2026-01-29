"""
logic.py - 战斗逻辑核心

包含：
- ActionGenerator: 三层查询 API，供 Controller 分步获取可行动作
- DamageCalculator: 伤害计算（使用 ECS 查询系统）
"""
import random
from typing import List, Dict, Optional
from .models import CombatAction, BattleContext, SkillTemplate
from .entity import CombatEntity
from .components import ResourceComponent, SkillsComponent
from .queries import StatQuery, EffectQuery
from .enums import ActionCategory, TargetType, DamageType, SkillCategory


class ActionGenerator:
    """
    三层查询 API，支持经典 RPG 的分步选择：
    
    Step 1: get_available_categories() -> 可用行为大类
    Step 2: get_available_skills()     -> 该大类下可用的具体技能
    Step 3: get_valid_targets()        -> 该技能可选的目标列表
    
    最后通过 build_action() 构造 CombatAction。
    """
    
    def __init__(self, skill_registry: Dict[str, SkillTemplate]):
        self.skill_registry = skill_registry
    
    # ========== Step 1: 获取可用的行为大类 ==========
    def get_available_categories(
        self, actor: CombatEntity, context: BattleContext
    ) -> List[ActionCategory]:
        """
        返回当前角色可用的行为大类。
        例如：被沉默 -> 不能用 MAGIC；没有道具 -> 不能用 ITEM。
        """
        categories = []
        
        # 攻击：只要有活着的敌人就可以
        if context.get_alive_enemies():
            categories.append(ActionCategory.ATTACK)
        
        # 法术：需要有可用的法术类技能，且未被沉默
        if self._has_usable_skills(actor, SkillCategory.MAGIC):
            # ECS: 检查沉默状态
            if not EffectQuery.is_silenced(actor):
                categories.append(ActionCategory.MAGIC)
        
        # 防御：总是可用
        categories.append(ActionCategory.DEFEND)
        
        # 物品：TODO 需要背包系统支持
        # if actor.has_usable_items():
        #     categories.append(ActionCategory.ITEM)
        
        # 逃跑：TODO 可以根据战斗类型决定
        # categories.append(ActionCategory.FLEE)
        
        return categories
    
    def _has_usable_skills(self, actor: CombatEntity, skill_cat: SkillCategory) -> bool:
        """检查角色是否有该类型的可用技能"""
        for skill_id in actor.known_skill_ids:
            skill = self.skill_registry.get(skill_id)
            if not skill:
                continue
            if skill.category != skill_cat:
                continue
            
            # 只要有这个类别的技能，就应该显示这个入口，哪怕当前不可用（比如没蓝、冷却中）
            # 用户点进去看到灰色的技能，可以知道为什么不能用，体验更好
            return True
            
            # 原来的逻辑：所有技能只要有一个能用才显示入口，否则完全隐藏
            # if self._can_use_skill(actor, skill):
            #    return True
        return False
    
    def _can_use_skill(self, actor: CombatEntity, skill: SkillTemplate) -> bool:
        """检查技能是否可用（消耗足够、冷却完毕）"""
        # ECS: 使用组件查询
        res = actor.get(ResourceComponent)
        skills_comp = actor.get(SkillsComponent)
        
        if not res:
            return False
        
        if res.current_mp < skill.cost_mp:
            return False
        if res.current_san < skill.cost_san:
            return False
        
        # 检查冷却
        if skills_comp:
            if skills_comp.cooldowns.get(skill.id, 0) > 0:
                return False
        
        return True
    
    # ========== Step 2: 获取该大类下可用的技能列表 ==========
    def get_available_skills(
        self, actor: CombatEntity, category: ActionCategory, context: BattleContext
    ) -> List[SkillTemplate]:
        """
        根据行为大类，返回可用的技能列表。
        
        - ATTACK: 返回攻击类技能（普攻在 UI 层单独处理）
        - MAGIC:  返回法术类技能
        - DEFEND: 无需进入此步（或返回空）
        """
        skills: List[SkillTemplate] = []
        
        if category == ActionCategory.ATTACK:
            for skill_id in actor.known_skill_ids:
                skill = self.skill_registry.get(skill_id)
                if not skill:
                    continue
                if skill.category != SkillCategory.ATTACK:
                    continue
                # 不在这里过滤可用性，交给上层处理（标记 is_usable）
                skills.append(skill)
        
        elif category == ActionCategory.MAGIC:
            for skill_id in actor.known_skill_ids:
                skill = self.skill_registry.get(skill_id)
                if not skill:
                    continue
                if skill.category != SkillCategory.MAGIC:
                    continue
                # 不在这里过滤可用性，交给上层处理（标记 is_usable）
                skills.append(skill)
        
        return skills
    
    # ========== Step 3: 获取技能可作用的目标列表 ==========
    def get_valid_targets(
        self, 
        actor: CombatEntity, 
        skill: Optional[SkillTemplate], 
        context: BattleContext
    ) -> List[CombatEntity]:
        """
        返回技能可以作用的目标列表。
        
        skill=None 表示普攻（默认打敌方单体）。
        群体技能返回全部合法目标。
        """
        if skill is None:
            # 普攻：单体敌人
            return context.get_alive_enemies()
        
        target_type = skill.target_type
        
        if target_type == TargetType.SELF:
            return [actor] if not actor.is_dead else []
        
        elif target_type == TargetType.SINGLE_ENEMY:
            return context.get_alive_enemies()
        
        elif target_type == TargetType.ALL_ENEMIES:
            return context.get_alive_enemies()
        
        elif target_type == TargetType.SINGLE_ALLY:
            return context.get_alive_allies()
        
        elif target_type == TargetType.ALL_ALLIES:
            return context.get_alive_allies()
        
        return []
    
    def is_aoe(self, skill: Optional[SkillTemplate]) -> bool:
        """判断技能是否为群体技能"""
        if skill is None:
            return False
        return skill.target_type in (TargetType.ALL_ENEMIES, TargetType.ALL_ALLIES)
    
    # ========== 构造最终 Action ==========
    def build_action(
        self,
        actor: CombatEntity,
        category: ActionCategory,
        skill: Optional[SkillTemplate],
        targets: List[CombatEntity]
    ) -> CombatAction:
        """组装最终的 CombatAction"""
        return CombatAction(
            source_id=actor.instance_id,
            category=category,
            skill_id=skill.id if skill else None,
            target_ids=[t.instance_id for t in targets]
        )
    
    # ========== 兼容旧 API（供 RandomAI 使用）==========
    def get_valid_actions(
        self, actor: CombatEntity, context: BattleContext
    ) -> List[CombatAction]:
        """
        一次性生成所有合法动作（笛卡尔积），供 AI 随机选择。
        保留此方法以兼容 RandomAIController。
        """
        actions: List[CombatAction] = []
        
        for category in self.get_available_categories(actor, context):
            if category == ActionCategory.DEFEND:
                actions.append(CombatAction(
                    source_id=actor.instance_id,
                    category=ActionCategory.DEFEND
                ))
                continue
            
            # 普攻（category=ATTACK, skill=None）
            if category == ActionCategory.ATTACK:
                for target in context.get_alive_enemies():
                    actions.append(CombatAction(
                        source_id=actor.instance_id,
                        category=ActionCategory.ATTACK,
                        skill_id=None,
                        target_ids=[target.instance_id]
                    ))
            
            # 技能 - AI 使用时需要过滤不可用的技能
            for skill in self.get_available_skills(actor, category, context):
                # AI 需要检查技能是否真的可用
                if not self._can_use_skill(actor, skill):
                    continue
                    
                targets = self.get_valid_targets(actor, skill, context)
                if not targets:
                    continue
                
                if self.is_aoe(skill):
                    actions.append(self.build_action(actor, category, skill, targets))
                else:
                    for t in targets:
                        actions.append(self.build_action(actor, category, skill, [t]))
        
        return actions


class DamageCalculator:
    """
    伤害计算核心
    
    使用 ECS 的 StatQuery 获取经过 Buff 修正后的属性值。
    """
    
    @staticmethod
    def calculate(
        attacker: CombatEntity, 
        target: CombatEntity, 
        skill: Optional[SkillTemplate]
    ) -> dict:
        """
        计算伤害/治疗结果。
        skill=None 表示普攻。
        
        返回值包含：
        - hit: bool
        - damage: int (伤害或治疗量)
        - is_crit: bool
        - type: "DAMAGE" | "HEAL"
        - damage_type: DamageType (实际的伤害/治疗类型)
        """
        # 普攻等价于 power_coef=1.0 的物理伤害
        if skill is None:
            power_coef = 1.0
            damage_type = DamageType.PHYSICAL
            fixed_value = 0
        else:
            power_coef = skill.power_coef
            damage_type = skill.damage_type
            fixed_value = skill.fixed_value
        
        # ECS: 使用 StatQuery 获取修正后的属性
        attacker_acc = StatQuery.get(attacker, "acc")
        target_eva = StatQuery.get(target, "eva")
        
        # 1. 命中判定
        hit_rate = (attacker_acc - target_eva) + 0.95
        if random.random() > hit_rate:
            return {
                "hit": False, 
                "damage": 0, 
                "is_crit": False, 
                "type": "DAMAGE",
                "damage_type": damage_type
            }
        
        # 2. 基础伤害计算（使用修正后的属性）
        base = 0.0
        defense = 0
        
        if damage_type == DamageType.PHYSICAL:
            base = StatQuery.get(attacker, "atk") * power_coef
            defense = StatQuery.get_int(target, "def_")
        
        elif damage_type == DamageType.MAGICAL:
            base = StatQuery.get(attacker, "matk") * power_coef
            defense = StatQuery.get_int(target, "mdef")
        
        elif damage_type == DamageType.MENTAL:
            base = StatQuery.get(attacker, "max_san") * 0.1 * power_coef
            defense = int(StatQuery.get(target, "mdef") * 0.5)
        
        elif damage_type == DamageType.HEAL:
            heal = StatQuery.get(attacker, "matk") * power_coef + fixed_value
            attacker_crit = StatQuery.get(attacker, "crit")
            is_crit = random.random() < attacker_crit
            if is_crit:
                heal *= 1.5
            return {
                "hit": True, 
                "damage": int(heal), 
                "is_crit": is_crit, 
                "type": "HEAL",
                "damage_type": damage_type
            }
        
        elif damage_type == DamageType.TRUE:
            base = StatQuery.get(attacker, "atk") * power_coef
            defense = 0
        
        # 加上固定伤害
        base += fixed_value
        
        # 3. 减伤 (简单除法公式)
        dmg = base / (1 + defense * 0.05)
        
        # 4. 暴击判定（使用修正后的属性）
        attacker_crit = StatQuery.get(attacker, "crit")
        target_anticrit = StatQuery.get(target, "anticrit")
        crit_chance = attacker_crit - target_anticrit
        is_crit = random.random() < crit_chance
        if is_crit:
            dmg *= 1.5
        
        # 5. 应用伤害修正（来自 Effect）
        dmg *= StatQuery.get_damage_dealt_modifier(attacker)
        dmg *= StatQuery.get_damage_received_modifier(target)
        
        # 6. 浮动 (±10%)
        dmg *= random.uniform(0.9, 1.1)
        
        return {
            "hit": True, 
            "damage": int(max(1, dmg)), 
            "is_crit": is_crit, 
            "type": "DAMAGE",
            "damage_type": damage_type
        }
