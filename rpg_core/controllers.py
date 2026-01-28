"""
controllers.py - 战斗控制器

包含：
- BaseController: 抽象基类
- RandomAIController: 随机 AI
- HumanCLIController: 三步交互的人类控制器 (stdin/stdout)
"""
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from .models import BattleContext, CombatAction, SkillTemplate, CombatEntity
from .logic import ActionGenerator
from .enums import ActionCategory, SkillCategory


class BaseController(ABC):
    """控制器基类"""
    
    @abstractmethod
    def select_action(self, context: BattleContext) -> CombatAction:
        """根据当前上下文，返回一个完整的动作指令"""
        pass


class RandomAIController(BaseController):
    """随机 AI：从所有合法动作中随机选一个"""
    
    def __init__(self, skill_registry: Dict[str, SkillTemplate]):
        self.generator = ActionGenerator(skill_registry)
    
    def select_action(self, context: BattleContext) -> CombatAction:
        options = self.generator.get_valid_actions(context.current_actor, context)
        
        if not options:
            return CombatAction(
                source_id=context.current_actor.instance_id, 
                category=ActionCategory.DEFEND
            )
        
        return random.choice(options)


class HumanCLIController(BaseController):
    """
    三步交互的人类控制器 (经典 RPG 风格):
    
    Step 1: 选择行为大类 (攻击/法术/防御/...)
    Step 2: 选择具体技能 (普通攻击/旋风斩/火球术/...)
    Step 3: 选择目标 (单体需选择，群体确认即可)
    
    支持输入 0 或 'b' 返回上一步。
    """
    
    CATEGORY_NAMES = {
        ActionCategory.ATTACK: "攻击",
        ActionCategory.MAGIC: "法术",
        ActionCategory.DEFEND: "防御",
        ActionCategory.ITEM: "物品",
        ActionCategory.FLEE: "逃跑",
    }
    
    def __init__(self, skill_registry: Dict[str, SkillTemplate]):
        self.skill_registry = skill_registry
        self.generator = ActionGenerator(skill_registry)
    
    def select_action(self, context: BattleContext) -> CombatAction:
        actor = context.current_actor
        
        while True:
            # Step 1: 选择行为大类
            category = self._step1_select_category(actor, context)
            if category is None:
                continue  # 不应该发生，但保险起见
            
            # 防御直接结束
            if category == ActionCategory.DEFEND:
                return self.generator.build_action(actor, category, None, [])
            
            # Step 2: 选择具体技能
            skill = self._step2_select_skill(actor, category, context)
            if skill == "BACK":
                continue  # 返回 Step 1
            
            # Step 3: 选择目标
            targets = self._step3_select_targets(actor, skill, context)
            if targets == "BACK":
                continue  # 返回 Step 1（简化起见不返回 Step 2）
            
            # 构造并返回
            return self.generator.build_action(actor, category, skill, targets)
    
    # ==================== Step 1 ====================
    def _step1_select_category(
        self, actor: CombatEntity, context: BattleContext
    ) -> Optional[ActionCategory]:
        """第一步：选择行为大类"""
        categories = self.generator.get_available_categories(actor, context)
        
        self._print_header(actor, context)
        print("\n【第一步】选择行动类型:")
        for i, cat in enumerate(categories, 1):
            print(f"  {i}. {self.CATEGORY_NAMES.get(cat, cat)}")
        
        while True:
            raw = input("请输入序号: ").strip()
            idx = self._parse_int(raw)
            if idx is not None and 1 <= idx <= len(categories):
                return categories[idx - 1]
            print("输入无效，请重新输入。")
    
    # ==================== Step 2 ====================
    def _step2_select_skill(
        self, actor: CombatEntity, category: ActionCategory, context: BattleContext
    ):
        """
        第二步：选择具体技能
        返回 SkillTemplate 或 None（普攻）或 "BACK"（返回上一步）
        """
        # 获取该类别的技能
        skills = self.generator.get_available_skills(actor, category, context)
        
        # 对于 ATTACK 类别，普攻作为默认选项
        has_basic_attack = (category == ActionCategory.ATTACK)
        
        print(f"\n【第二步】选择{self.CATEGORY_NAMES.get(category, category)}:")
        print("  0. ← 返回上一步")
        
        offset = 1
        if has_basic_attack:
            print("  1. 普通攻击")
            offset = 2
        
        for i, skill in enumerate(skills, offset):
            cost_str = self._format_cost(skill)
            cd_str = self._format_cd(actor, skill)
            print(f"  {i}. {skill.name} {cost_str}{cd_str}")
        
        total_options = (1 if has_basic_attack else 0) + len(skills)
        
        while True:
            raw = input("请输入序号: ").strip()
            if raw.lower() in ('0', 'b', 'back'):
                return "BACK"
            
            idx = self._parse_int(raw)
            if idx is None:
                print("输入无效，请重新输入。")
                continue
            
            if has_basic_attack and idx == 1:
                return None  # 普攻
            
            skill_idx = idx - offset
            if 0 <= skill_idx < len(skills):
                return skills[skill_idx]
            
            print("输入无效，请重新输入。")
    
    # ==================== Step 3 ====================
    def _step3_select_targets(
        self, actor: CombatEntity, skill: Optional[SkillTemplate], context: BattleContext
    ):
        """
        第三步：选择目标
        返回 List[CombatEntity] 或 "BACK"
        """
        targets = self.generator.get_valid_targets(actor, skill, context)
        is_aoe = self.generator.is_aoe(skill)
        
        skill_name = skill.name if skill else "普通攻击"
        
        if is_aoe:
            # 群体技能：确认释放
            target_names = ", ".join(t.name for t in targets)
            print(f"\n【第三步】{skill_name} 将作用于: {target_names}")
            print("  0. ← 返回")
            print("  1. 确认释放")
            
            while True:
                raw = input("请输入序号: ").strip()
                if raw.lower() in ('0', 'b', 'back'):
                    return "BACK"
                if raw == '1':
                    return targets
                print("输入无效，请重新输入。")
        
        else:
            # 单体技能：选择目标
            print(f"\n【第三步】选择 {skill_name} 的目标:")
            print("  0. ← 返回")
            for i, t in enumerate(targets, 1):
                hp_str = f"HP {t.current_hp}/{t.stats.max_hp}"
                print(f"  {i}. {t.name} ({hp_str})")
            
            while True:
                raw = input("请输入序号: ").strip()
                if raw.lower() in ('0', 'b', 'back'):
                    return "BACK"
                
                idx = self._parse_int(raw)
                if idx is not None and 1 <= idx <= len(targets):
                    return [targets[idx - 1]]
                
                print("输入无效，请重新输入。")
    
    # ==================== 辅助方法 ====================
    def _print_header(self, actor: CombatEntity, context: BattleContext):
        """打印回合头部信息"""
        print("\n" + "=" * 50)
        print(f"【{actor.name} 的回合】")
        print(f"HP: {actor.current_hp}/{actor.stats.max_hp}  "
              f"MP: {actor.current_mp}/{actor.stats.max_mp}")
        print("-" * 50)
        
        # 我方状态
        print("我方: ", end="")
        ally_strs = [self._format_unit_brief(u) for u in context.allies]
        print("  ".join(ally_strs))
        
        # 敌方状态
        print("敌方: ", end="")
        enemy_strs = [self._format_unit_brief(u) for u in context.enemies]
        print("  ".join(enemy_strs))
    
    def _format_unit_brief(self, u: CombatEntity) -> str:
        if u.is_dead:
            return f"{u.name}(DEAD)"
        return f"{u.name}({u.current_hp}/{u.stats.max_hp})"
    
    def _format_cost(self, skill: SkillTemplate) -> str:
        parts = []
        if skill.cost_mp:
            parts.append(f"MP:{skill.cost_mp}")
        if skill.cost_san:
            parts.append(f"SAN:{skill.cost_san}")
        return f"[{' '.join(parts)}]" if parts else ""
    
    def _format_cd(self, actor: CombatEntity, skill: SkillTemplate) -> str:
        cd = actor.cooldowns.get(skill.id, 0)
        if cd > 0:
            return f" (CD:{cd})"
        return ""
    
    @staticmethod
    def _parse_int(s: str) -> Optional[int]:
        try:
            return int(s)
        except ValueError:
            return None
