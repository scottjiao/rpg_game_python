"""
engine.py - 战斗引擎（Sans-IO / Passive 设计）

BattleEngine 是一个纯粹的状态机，只负责战斗逻辑计算，不负责"驱动循环"和"等待输入"。
外部调用方（main.py 或 GameBridge）负责：
1. 循环调用引擎的单步方法
2. 获取玩家/AI 的输入
3. 将输入传递给引擎执行

这样无论是同步 CLI 还是异步 WebSocket，都可以复用同一套战斗逻辑。
"""
from typing import List, Dict, Optional
from .models import CombatEntity, BattleContext, SkillTemplate, CombatAction
from .events import EventBus, TurnEvent, DamageEvent, LogEvent, BattleEndEvent, EventType
from .logic import DamageCalculator
from .enums import ActionCategory
from .events import BaseEvent


class BattleEngine:
    """
    战斗引擎（状态机模式）
    
    提供细粒度的单步执行 API，不包含任何循环或 IO 操作。
    所有方法都是同步的、纯计算的，执行时间极短。
    """
    
    def __init__(self, bus: EventBus, skill_registry: Dict[str, SkillTemplate]):
        self.bus = bus
        self.skill_registry = skill_registry
        
        # 状态
        self.allies: List[CombatEntity] = []
        self.enemies: List[CombatEntity] = []
        self.entities_map: Dict[str, CombatEntity] = {}
        self.turn_count = 0
        self.is_battle_over = False
        self.winner_team: Optional[str] = None

    def initialize(self, allies: List[CombatEntity], enemies: List[CombatEntity]):
        """
        初始化战斗状态
        
        注意：不再接收 controllers 参数，控制器由外部调用方管理。
        """
        self.allies = allies
        self.enemies = enemies
        self.entities_map = {e.instance_id: e for e in allies + enemies}
        self.turn_count = 0
        self.is_battle_over = False
        self.winner_team = None
        self.bus.publish(LogEvent(message="战斗初始化完成！"))

    def start_battle(self):
        """开始战斗（发布战斗开始事件）"""
        self.bus.publish(LogEvent(message="--- 战斗开始 ---"))

    def get_turn_order(self) -> List[CombatEntity]:
        """
        计算本回合的行动顺序
        
        Returns:
            按速度降序排列的存活单位列表
        """
        all_units = self.allies + self.enemies
        active_units = [u for u in all_units if not u.is_dead]
        active_units.sort(key=lambda u: u.stats.spd, reverse=True)
        return active_units

    def increment_turn(self):
        """增加回合计数"""
        self.turn_count += 1

    def start_turn(self, actor: CombatEntity) -> BattleContext:
        """
        回合开始结算
        
        执行以下操作：
        1. 发布回合开始事件
        2. 减少技能冷却
        3. TODO: 结算 DoT/Buff
        4. 构建并返回战斗上下文
        
        Args:
            actor: 当前行动的单位
            
        Returns:
            BattleContext: 供控制器做决策的战场快照
        """
        # 1. 发布回合开始事件
        self.bus.publish(TurnEvent(
            turn_number=self.turn_count,
            actor_id=actor.instance_id,
            actor_name=actor.name
        ))

        # 2. 减少冷却
        for sk_id in list(actor.cooldowns.keys()):
            if actor.cooldowns[sk_id] > 0:
                actor.cooldowns[sk_id] -= 1

        # 3. TODO: 结算 DoT/Buff（可在此处扩展）

        # 4. 构建上下文
        context = BattleContext(
            turn_number=self.turn_count,
            current_actor=actor,
            allies=self.allies if actor in self.allies else self.enemies,
            enemies=self.enemies if actor in self.allies else self.allies
        )

        return context

    def resolve_action(self, actor: CombatEntity, action: CombatAction, context: BattleContext):
        """
        执行具体的动作
        
        根据传入的 action 进行伤害计算、扣血、发布事件。
        这里全是纯计算，不涉及任何 IO 操作。
        
        Args:
            actor: 执行动作的单位
            action: 要执行的动作指令
            context: 战斗上下文
        """
        self._execute_action(actor, action, context)

    def check_battle_end(self) -> Optional[str]:
        """
        检查战斗是否结束
        
        Returns:
            胜利方标识（"ALLIES" 或 "ENEMIES"），如果战斗未结束则返回 None
        """
        if all(u.is_dead for u in self.allies):
            self.is_battle_over = True
            self.winner_team = "ENEMIES"
            self.bus.publish(BattleEndEvent(winner_team="ENEMIES"))
            return "ENEMIES"
        elif all(u.is_dead for u in self.enemies):
            self.is_battle_over = True
            self.winner_team = "ALLIES"
            self.bus.publish(BattleEndEvent(winner_team="ALLIES"))
            return "ALLIES"
        return None

    def get_entity(self, entity_id: str) -> Optional[CombatEntity]:
        """根据 ID 获取实体"""
        return self.entities_map.get(entity_id)

    def is_ally(self, entity: CombatEntity) -> bool:
        """判断实体是否属于友方"""
        return entity in self.allies

    # ==================== 内部方法 ====================

    def _execute_action(self, actor: CombatEntity, action: CombatAction, context: BattleContext):
        """
        执行动作的内部实现
        
        处理伤害计算、资源消耗、冷却设置等。
        """
        # 获取技能模板
        skill_tmpl = self.skill_registry.get(action.skill_id) if action.skill_id else None
        
        # 决定显示名
        if action.category == ActionCategory.DEFEND:
            skill_name = "防御"
        elif skill_tmpl:
            skill_name = skill_tmpl.name
        else:
            skill_name = "普通攻击"
        
        self.bus.publish(LogEvent(message=f"{actor.name} 使用了 {skill_name}！"))

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