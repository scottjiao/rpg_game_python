import time
from typing import List, Dict
from .models import CombatEntity, BattleContext, SkillTemplate, CombatAction
from .events import EventBus, TurnEvent, DamageEvent, LogEvent, BattleEndEvent, EventType
from .logic import DamageCalculator
from .controllers import BaseController
from .enums import ActionCategory
from .events import BaseEvent

class BattleEngine:
    def __init__(self, bus: EventBus, skill_registry: Dict[str, SkillTemplate]):
        self.bus = bus
        self.skill_registry = skill_registry
        
        # 状态
        self.allies: List[CombatEntity] = []
        self.enemies: List[CombatEntity] = []
        self.turn_count = 0
        self.is_battle_over = False
        
        # ID -> Controller 映射
        self.controllers: Dict[str, BaseController] = {}

    def initialize(self, allies: List[CombatEntity], enemies: List[CombatEntity], controllers: Dict[str, BaseController]):
        self.allies = allies
        self.enemies = enemies
        self.controllers = controllers
        self.bus.publish(LogEvent(message="战斗初始化完成！"))

    def run_battle_loop(self):
        """主战斗循环"""
        self.bus.publish(LogEvent(message="--- 战斗开始 ---"))
        
        while not self.is_battle_over:
            self.turn_count += 1
            
            # 简单的速度排序机制 (Speed order)
            all_units = self.allies + self.enemies
            # 过滤死人
            active_units = [u for u in all_units if not u.is_dead]
            # 按速度降序
            active_units.sort(key=lambda u: u.stats.spd, reverse=True)

            if not active_units:
                break

            for unit in active_units:
                if self.is_battle_over: break
                if unit.is_dead: continue # 可能在这个回合被之前的人打死了

                self._process_turn(unit)
                
                # 胜负判定
                if all(u.is_dead for u in self.allies):
                    self.is_battle_over = True
                    self.bus.publish(BattleEndEvent(winner_team="ENEMIES"))
                elif all(u.is_dead for u in self.enemies):
                    self.is_battle_over = True
                    self.bus.publish(BattleEndEvent(winner_team="ALLIES"))

    def _process_turn(self, actor: CombatEntity):
        # 1. 回合开始事件 (处理 DoT/Buff 可以在这里监听)
        self.bus.publish(TurnEvent(turn_number=self.turn_count, actor_id=actor.instance_id, actor_name=actor.name))

        # 2. 减少冷却
        for sk_id in list(actor.cooldowns.keys()):
            if actor.cooldowns[sk_id] > 0:
                actor.cooldowns[sk_id] -= 1

        # 3. 构建上下文
        context = BattleContext(
            turn_number=self.turn_count,
            current_actor=actor,
            allies=self.allies if actor in self.allies else self.enemies,
            enemies=self.enemies if actor in self.allies else self.allies
        )

        # 4. 获取控制器决策
        controller = self.controllers.get(actor.instance_id)
        if not controller:
            # Fallback
            self.bus.publish(LogEvent(message=f"Error: No controller for {actor.name}"))
            return

        action = controller.select_action(context)
        
        # 5. 执行动作
        self._execute_action(actor, action, context)

    def _execute_action(self, actor: CombatEntity, action: CombatAction, context: BattleContext):
        # 获取技能模板
        skill_tmpl = self.skill_registry.get(action.skill_id) if action.skill_id else None
        
        # 决定显示名
        if action.category == ActionCategory.DEFEND:
            skill_name = "防御"
        elif skill_tmpl:
            skill_name = skill_tmpl.name
        else:
            skill_name = "普通攻击"
        
        self.bus.publish(LogEvent(message=f"Decision: {actor.name} 选择了 [{action.category.value}] -> {skill_name}"))

        # 防御处理
        if action.category == ActionCategory.DEFEND:
            actor.current_mp = min(actor.stats.max_mp, actor.current_mp + 5)
            self.bus.publish(LogEvent(message=f"{actor.name} 进行防御，恢复了少量体力。"))
            return

        # 如果有技能，扣消耗、设冷却
        if skill_tmpl:
            actor.current_mp -= skill_tmpl.cost_mp
            actor.current_san -= skill_tmpl.cost_san
            if skill_tmpl.cooldown > 0:
                actor.cooldowns[skill_tmpl.id] = skill_tmpl.cooldown

        # 遍历目标进行结算 (skill_tmpl=None 时 DamageCalculator 视为普攻)
        for tid in action.target_ids:
            target = context.get_entity(tid)
            if not target or target.is_dead:
                continue

            result = DamageCalculator.calculate(actor, target, skill_tmpl)
            
            if not result["hit"]:
                self.bus.publish(LogEvent(message=f"MISS! {actor.name} 未命中 {target.name}"))
                continue

            if result["type"] == "HEAL":
                target.current_hp = min(target.stats.max_hp, target.current_hp + result["damage"])
                self.bus.publish(DamageEvent(
                    type=EventType.HEAL_DEALT, source_id=actor.instance_id, target_id=target.instance_id,
                    amount=result["damage"], is_crit=result["is_crit"], damage_type=result["damage_type"]
                ))
            else:
                target.current_hp = max(0, target.current_hp - result["damage"])
                if target.current_hp == 0:
                    target.is_dead = True
                
                self.bus.publish(DamageEvent(
                    source_id=actor.instance_id, target_id=target.instance_id,
                    amount=result["damage"], is_crit=result["is_crit"], damage_type=result["damage_type"]
                ))
                if target.is_dead:
                    self.bus.publish(BaseEvent(type=EventType.UNIT_DEATH))