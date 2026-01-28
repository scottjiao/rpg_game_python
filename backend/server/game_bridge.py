"""
game_bridge.py - 游戏桥接器

连接 rpg_core 核心逻辑与 WebSocket 网络层。
- 订阅 EventBus 事件，转换为网络消息发送给前端
- 管理异步战斗流程
"""
import asyncio
from typing import Dict, List, Callable, Awaitable, Optional, Any

from rpg_core.enums import TargetType, DamageType, EventType, SkillCategory
from rpg_core.models import CharacterTemplate, SkillTemplate, CombatEntity, BattleStats, BattleContext, CombatAction
from rpg_core.events import EventBus, DamageEvent, LogEvent, BattleEndEvent, TurnEvent, BaseEvent
from rpg_core.controllers import RandomAIController, BaseController
from rpg_core.logic import ActionGenerator, DamageCalculator

from .protocol import (
    ServerMessage, ServerMsgType, ClientMsgType,
    InitStateData, UnitInfo, DamageData, HealData, TurnStartData, BattleEndData
)
from .websocket_controller import WebSocketController


class GameBridge:
    """
    游戏桥接器：连接核心逻辑与网络层
    
    职责：
    1. 管理战斗状态
    2. 订阅 EventBus，将事件转换为 WebSocket 消息
    3. 处理前端指令，驱动战斗流程
    """
    
    def __init__(self, send_func: Callable[[dict], Awaitable[None]]):
        """
        Args:
            send_func: 异步发送 WebSocket 消息的函数
        """
        self.send = send_func
        self.bus = EventBus()
        self.skill_registry: Dict[str, SkillTemplate] = {}
        
        # 战斗状态
        self.allies: List[CombatEntity] = []
        self.enemies: List[CombatEntity] = []
        self.entities_map: Dict[str, CombatEntity] = {}
        self.controllers: Dict[str, BaseController] = {}
        self.ws_controllers: Dict[str, WebSocketController] = {}
        
        # 战斗控制
        self.turn_count = 0
        self.is_battle_over = False
        self.current_actor: Optional[CombatEntity] = None
        
        # 订阅事件
        self._subscribe_events()
    
    def _subscribe_events(self):
        """订阅 EventBus 事件"""
        self.bus.subscribe(EventType.LOG, self._on_log)
        self.bus.subscribe(EventType.DAMAGE_DEALT, self._on_damage)
        self.bus.subscribe(EventType.HEAL_DEALT, self._on_heal)
        self.bus.subscribe(EventType.TURN_START, self._on_turn_start)
        self.bus.subscribe(EventType.UNIT_DEATH, self._on_unit_death)
        self.bus.subscribe(EventType.BATTLE_END, self._on_battle_end)
    
    # ==================== 事件处理器 ====================
    
    def _on_log(self, event: LogEvent):
        """处理日志事件"""
        asyncio.create_task(self.send({
            "type": ServerMsgType.LOG.value,
            "data": {"message": event.message}
        }))
    
    def _on_damage(self, event: DamageEvent):
        """处理伤害事件"""
        target = self.entities_map.get(event.target_id)
        source = self.entities_map.get(event.source_id)
        
        asyncio.create_task(self.send({
            "type": ServerMsgType.DAMAGE.value,
            "data": DamageData(
                source_id=event.source_id,
                source_name=source.name if source else "???",
                target_id=event.target_id,
                target_name=target.name if target else "???",
                amount=event.amount,
                is_crit=event.is_crit,
                damage_type=event.damage_type,
                remaining_hp=target.current_hp if target else 0,
                max_hp=target.stats.max_hp if target else 0
            ).model_dump()
        }))
        
        # 同时发送 HP 更新
        if target:
            asyncio.create_task(self.send({
                "type": ServerMsgType.UPDATE_HP.value,
                "data": {
                    "unit_id": target.instance_id,
                    "current_hp": target.current_hp,
                    "max_hp": target.stats.max_hp
                }
            }))
    
    def _on_heal(self, event: DamageEvent):
        """处理治疗事件"""
        target = self.entities_map.get(event.target_id)
        source = self.entities_map.get(event.source_id)
        
        asyncio.create_task(self.send({
            "type": ServerMsgType.HEAL.value,
            "data": HealData(
                source_id=event.source_id,
                source_name=source.name if source else "???",
                target_id=event.target_id,
                target_name=target.name if target else "???",
                amount=event.amount,
                remaining_hp=target.current_hp if target else 0,
                max_hp=target.stats.max_hp if target else 0
            ).model_dump()
        }))
        
        # 同时发送 HP 更新
        if target:
            asyncio.create_task(self.send({
                "type": ServerMsgType.UPDATE_HP.value,
                "data": {
                    "unit_id": target.instance_id,
                    "current_hp": target.current_hp,
                    "max_hp": target.stats.max_hp
                }
            }))
    
    def _on_turn_start(self, event: TurnEvent):
        """处理回合开始事件"""
        asyncio.create_task(self.send({
            "type": ServerMsgType.TURN_START.value,
            "data": TurnStartData(
                turn_number=event.turn_number,
                actor_id=event.actor_id,
                actor_name=event.actor_name
            ).model_dump()
        }))
    
    def _on_unit_death(self, event: BaseEvent):
        """处理单位死亡事件"""
        # 找出刚死亡的单位
        for entity in self.entities_map.values():
            if entity.is_dead:
                asyncio.create_task(self.send({
                    "type": ServerMsgType.UNIT_DIED.value,
                    "data": {
                        "unit_id": entity.instance_id,
                        "unit_name": entity.name
                    }
                }))
    
    def _on_battle_end(self, event: BattleEndEvent):
        """处理战斗结束事件"""
        self.is_battle_over = True
        winner = "allies" if event.winner_team == "ALLIES" else "enemies"
        message = "我方胜利！" if winner == "allies" else "我方战败..."
        
        asyncio.create_task(self.send({
            "type": ServerMsgType.BATTLE_END.value,
            "data": BattleEndData(
                winner=winner,
                message=message
            ).model_dump()
        }))
    
    # ==================== 初始化 ====================
    
    def _create_mock_data(self):
        """创建测试数据"""
        skills = [
            SkillTemplate(
                id="fireball", name="火球术",
                category=SkillCategory.MAGIC,
                cost_mp=10, cooldown=0,
                target_type=TargetType.SINGLE_ENEMY,
                damage_type=DamageType.MAGICAL, power_coef=2.5
            ),
            SkillTemplate(
                id="heal", name="次级治疗",
                category=SkillCategory.MAGIC,
                cost_mp=40, cooldown=2,
                target_type=TargetType.SINGLE_ALLY,
                damage_type=DamageType.HEAL, power_coef=3.0
            ),
            SkillTemplate(
                id="slash", name="旋风斩",
                category=SkillCategory.ATTACK,
                cost_mp=20, cooldown=3,
                target_type=TargetType.ALL_ENEMIES,
                damage_type=DamageType.PHYSICAL, power_coef=0.8
            ),
            SkillTemplate(
                id="power_strike", name="强力攻击",
                category=SkillCategory.ATTACK,
                cost_mp=5, cooldown=0,
                target_type=TargetType.SINGLE_ENEMY,
                damage_type=DamageType.PHYSICAL, power_coef=1.5
            ),
        ]
        self.skill_registry = {s.id: s for s in skills}
        
        # 角色模板
        hero_stats = BattleStats(max_hp=200, max_mp=50, max_san=100, atk=20, matk=10, spd=12, acc=1.2, crit=0.2, def_=5)
        hero_tmpl = CharacterTemplate(id="hero", name="勇者", base_stats=hero_stats, skill_ids=["slash", "power_strike", "heal"])
        
        mage_stats = BattleStats(max_hp=120, max_mp=100, max_san=80, atk=5, matk=30, spd=10, acc=1.0, crit=0.3, def_=2)
        mage_tmpl = CharacterTemplate(id="mage", name="法师", base_stats=mage_stats, skill_ids=["fireball", "heal"])
        
        boss_stats = BattleStats(max_hp=600, max_mp=999, atk=25, matk=10, spd=8, acc=0.9, def_=8, mdef=5)
        boss_tmpl = CharacterTemplate(id="dragon", name="恶龙", base_stats=boss_stats, skill_ids=["fireball"])
        
        return hero_tmpl, mage_tmpl, boss_tmpl
    
    async def initialize_battle(self):
        """初始化战斗"""
        hero_tmpl, mage_tmpl, boss_tmpl = self._create_mock_data()
        
        # 创建实体
        hero = CombatEntity.create(hero_tmpl)
        mage = CombatEntity.create(mage_tmpl)
        boss = CombatEntity.create(boss_tmpl)
        
        self.allies = [hero, mage]
        self.enemies = [boss]
        self.entities_map = {e.instance_id: e for e in [hero, mage, boss]}
        
        # 创建控制器
        # 玩家角色使用 WebSocket 控制器
        for ally in self.allies:
            ws_ctrl = WebSocketController(self.skill_registry, self.send, ally.instance_id)
            self.controllers[ally.instance_id] = ws_ctrl
            self.ws_controllers[ally.instance_id] = ws_ctrl
        
        # 敌人使用 AI 控制器
        for enemy in self.enemies:
            self.controllers[enemy.instance_id] = RandomAIController(self.skill_registry)
        
        # 重置状态
        self.turn_count = 0
        self.is_battle_over = False
        
        # 发送初始状态
        await self._send_init_state()
        
        self.bus.publish(LogEvent(message="战斗初始化完成！"))
    
    async def _send_init_state(self):
        """发送初始状态给前端"""
        allies_info = [
            UnitInfo(
                id=e.instance_id,
                name=e.name,
                current_hp=e.current_hp,
                max_hp=e.stats.max_hp,
                current_mp=e.current_mp,
                max_mp=e.stats.max_mp,
                is_dead=e.is_dead,
                team="ally"
            )
            for e in self.allies
        ]
        
        enemies_info = [
            UnitInfo(
                id=e.instance_id,
                name=e.name,
                current_hp=e.current_hp,
                max_hp=e.stats.max_hp,
                current_mp=e.current_mp,
                max_mp=e.stats.max_mp,
                is_dead=e.is_dead,
                team="enemy"
            )
            for e in self.enemies
        ]
        
        await self.send({
            "type": ServerMsgType.INIT_STATE.value,
            "data": InitStateData(
                allies=allies_info,
                enemies=enemies_info,
                turn_number=self.turn_count
            ).model_dump()
        })
    
    # ==================== 战斗流程 ====================
    
    async def run_battle_loop(self):
        """主战斗循环（异步版本）"""
        self.bus.publish(LogEvent(message="--- 战斗开始 ---"))
        
        while not self.is_battle_over:
            self.turn_count += 1
            
            # 速度排序
            all_units = self.allies + self.enemies
            active_units = [u for u in all_units if not u.is_dead]
            active_units.sort(key=lambda u: u.stats.spd, reverse=True)
            
            if not active_units:
                break
            
            for unit in active_units:
                if self.is_battle_over:
                    break
                if unit.is_dead:
                    continue
                
                await self._process_turn(unit)
                
                # 胜负判定
                if all(u.is_dead for u in self.allies):
                    self.is_battle_over = True
                    self.bus.publish(BattleEndEvent(winner_team="ENEMIES"))
                elif all(u.is_dead for u in self.enemies):
                    self.is_battle_over = True
                    self.bus.publish(BattleEndEvent(winner_team="ALLIES"))
                
                # 给前端一点时间处理动画
                await asyncio.sleep(0.3)
    
    async def _process_turn(self, actor: CombatEntity):
        """处理单个回合"""
        self.current_actor = actor
        
        # 1. 发送回合开始事件
        self.bus.publish(TurnEvent(
            turn_number=self.turn_count,
            actor_id=actor.instance_id,
            actor_name=actor.name
        ))
        
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
            self.bus.publish(LogEvent(message=f"Error: No controller for {actor.name}"))
            return
        
        # 根据控制器类型选择同步或异步
        if isinstance(controller, WebSocketController):
            action = await controller.select_action_async(context)
        else:
            action = controller.select_action(context)
        
        # 5. 执行动作
        await self._execute_action(actor, action, context)
    
    async def _execute_action(self, actor: CombatEntity, action: CombatAction, context: BattleContext):
        """执行动作"""
        from rpg_core.enums import ActionCategory
        
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
        
        # 扣消耗、设冷却
        if skill_tmpl:
            actor.current_mp -= skill_tmpl.cost_mp
            actor.current_san -= skill_tmpl.cost_san
            if skill_tmpl.cooldown > 0:
                actor.cooldowns[skill_tmpl.id] = skill_tmpl.cooldown
            
            # 关键修复：扣除MP后，立即发送 MP 更新事件给前台
            asyncio.create_task(self.send({
                "type": ServerMsgType.UPDATE_HP.value, # 注意：我偷懒复用了UPDATE_HP消息来更新所有状态
                "data": {
                    "unit_id": actor.instance_id,
                    "current_hp": actor.current_hp,
                    "max_hp": actor.stats.max_hp,
                    # 虽然协议里复用了UPDATE_HP的结构，但我们需要确保前端能读到最新的MP
                    # 实际上我们需要发送一个新的 UPDATE_MP 或者确保前端处理 UPDATE_HP 时也会更新 MP
                    # 查看 frontend/game.js: handleUpdateHP 只更新了 hp。
                    # 所以我们需要发送 UPDATE_MP
                }
            }))
            
            # 发送 MP 更新
            asyncio.create_task(self.send({
                "type": ServerMsgType.UPDATE_MP.value,
                "data": {
                    "unit_id": actor.instance_id,
                    "current_mp": actor.current_mp,
                    "max_mp": actor.stats.max_mp
                }
            }))
        
        # 遍历目标进行结算
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
                    type=EventType.HEAL_DEALT,
                    source_id=actor.instance_id,
                    target_id=target.instance_id,
                    amount=result["damage"],
                    is_crit=result["is_crit"],
                    damage_type=result["damage_type"]
                ))
            else:
                target.current_hp = max(0, target.current_hp - result["damage"])
                if target.current_hp == 0:
                    target.is_dead = True
                
                self.bus.publish(DamageEvent(
                    source_id=actor.instance_id,
                    target_id=target.instance_id,
                    amount=result["damage"],
                    is_crit=result["is_crit"],
                    damage_type=result["damage_type"]
                ))
                
                if target.is_dead:
                    self.bus.publish(BaseEvent(type=EventType.UNIT_DEATH))
            
            # 动画间隔
            await asyncio.sleep(0.2)
    
    # ==================== 客户端消息处理 ====================
    
    def handle_client_message(self, msg_type: ClientMsgType, data: Dict[str, Any]):
        """
        处理来自客户端的消息
        """
        # 将消息路由到对应的 WebSocket 控制器
        if msg_type in (ClientMsgType.SELECT_CATEGORY, ClientMsgType.SELECT_SKILL, ClientMsgType.SELECT_TARGET):
            if self.current_actor:
                ctrl = self.ws_controllers.get(self.current_actor.instance_id)
                if ctrl:
                    ctrl.receive_client_message(msg_type, data)
