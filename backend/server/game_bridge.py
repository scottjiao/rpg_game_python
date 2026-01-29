"""
game_bridge.py - 游戏桥接器

连接 rpg_core 核心逻辑与 WebSocket 网络层。
- 订阅 EventBus 事件，转换为网络消息发送给前端
- 管理异步战斗流程
- 复用 BattleEngine 的逻辑，只负责异步驱动

设计原则（Sans-IO）：
- BattleEngine 是纯状态机，不涉及任何 IO
- GameBridge 负责异步驱动、网络通信
- 战斗规则只在 BattleEngine 中定义一次
"""
import asyncio
from typing import Dict, List, Callable, Awaitable, Optional, Any

from rpg_core.enums import TargetType, DamageType, EventType, SkillCategory
from rpg_core.models import CharacterTemplate, SkillTemplate, CombatEntity, BattleStats
from rpg_core.events import EventBus, DamageEvent, LogEvent, TurnEvent, BattleEndEvent, BaseEvent
from rpg_core.controllers import RandomAIController, BaseController
from rpg_core.engine import BattleEngine

from .protocol import (
    ServerMsgType, ClientMsgType,
    InitStateData, UnitInfo, DamageData, HealData, TurnStartData, BattleEndData
)
from .websocket_controller import WebSocketController


class GameBridge:
    """
    游戏桥接器：连接核心逻辑与网络层
    
    职责：
    1. 管理战斗状态
    2. 订阅 EventBus，将事件转换为 WebSocket 消息
    3. 异步驱动 BattleEngine（调用其单步方法）
    4. 处理前端指令
    """
    
    def __init__(self, send_func: Callable[[dict], Awaitable[None]]):
        """
        Args:
            send_func: 异步发送 WebSocket 消息的函数
        """
        self.send = send_func
        self.bus = EventBus()
        self.skill_registry: Dict[str, SkillTemplate] = {}
        
        # 战斗引擎（复用核心逻辑）
        self.engine: Optional[BattleEngine] = None
        
        # 控制器（由 GameBridge 管理，不传给 Engine）
        self.controllers: Dict[str, BaseController] = {}
        self.ws_controllers: Dict[str, WebSocketController] = {}
        
        # 当前行动单位（用于路由客户端消息）
        self.current_actor: Optional[CombatEntity] = None
        
        # 订阅事件
        self._subscribe_events()
    
    @property
    def allies(self) -> List[CombatEntity]:
        """获取友方单位列表"""
        return self.engine.allies if self.engine else []
    
    @property
    def enemies(self) -> List[CombatEntity]:
        """获取敌方单位列表"""
        return self.engine.enemies if self.engine else []
    
    @property
    def entities_map(self) -> Dict[str, CombatEntity]:
        """获取实体映射"""
        return self.engine.entities_map if self.engine else {}
    
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
        
        allies = [hero, mage]
        enemies = [boss]
        
        # 创建引擎并初始化
        self.engine = BattleEngine(self.bus, self.skill_registry)
        self.engine.initialize(allies=allies, enemies=enemies)
        
        # 创建控制器（由 GameBridge 管理）
        # 玩家角色使用 WebSocket 控制器
        for ally in allies:
            ws_ctrl = WebSocketController(self.skill_registry, self.send, ally.instance_id)
            self.controllers[ally.instance_id] = ws_ctrl
            self.ws_controllers[ally.instance_id] = ws_ctrl
        
        # 敌人使用 AI 控制器
        for enemy in enemies:
            self.controllers[enemy.instance_id] = RandomAIController(self.skill_registry)
        
        # 发送初始状态
        await self._send_init_state()
    
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
                turn_number=self.engine.turn_count if self.engine else 0
            ).model_dump()
        })
    
    # ==================== 战斗流程 ====================
    
    async def run_battle_loop(self):
        """
        主战斗循环（异步版本）
        
        复用 BattleEngine 的逻辑，只负责：
        1. 异步驱动（循环）
        2. 异步获取玩家输入
        3. 发送状态更新给前端
        """
        if not self.engine:
            return
        
        # 开始战斗
        self.engine.start_battle()
        
        while not self.engine.is_battle_over:
            self.engine.increment_turn()
            
            # 复用引擎的排序逻辑
            units = self.engine.get_turn_order()
            
            if not units:
                break
            
            for unit in units:
                if self.engine.is_battle_over:
                    break
                if unit.is_dead:
                    continue
                
                self.current_actor = unit
                
                # 1. 引擎准备：回合开始结算，获取上下文
                context = self.engine.start_turn(unit)
                
                # 2. 获取输入（异步等待！）
                controller = self.controllers.get(unit.instance_id)
                if not controller:
                    continue
                
                if isinstance(controller, WebSocketController):
                    # 等待前端发包
                    action = await controller.select_action_async(context)
                else:
                    # AI 仍然是同步的
                    action = controller.select_action(context)
                
                # 3. 引擎执行（纯计算，即便在异步函数里调用同步函数也是安全的）
                self.engine.resolve_action(unit, action, context)
                
                # 发送 MP 更新（技能消耗后）
                await self._send_mp_update(unit)
                
                # 4. 检查结束
                if self.engine.check_battle_end():
                    break
                
                # 给前端一点时间处理动画
                await asyncio.sleep(0.3)
    
    async def _send_mp_update(self, unit: CombatEntity):
        """发送 MP 更新给前端"""
        await self.send({
            "type": ServerMsgType.UPDATE_MP.value,
            "data": {
                "unit_id": unit.instance_id,
                "current_mp": unit.current_mp,
                "max_mp": unit.stats.max_mp
            }
        })
    
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
