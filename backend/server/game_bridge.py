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

ECS 重构：
- 使用 Entity + Component 架构
- 通过组件查询获取属性

数据驱动：
- 技能、角色、战斗配置从 JSON 加载
- 特殊效果通过 Effect 系统实现
"""
import asyncio
from typing import Dict, List, Callable, Awaitable, Optional, Any

from rpg_core.enums import TargetType, DamageType, EventType, SkillCategory
from rpg_core.models import CharacterTemplate, SkillTemplate, BattleStats
from rpg_core.entity import CombatEntity
from rpg_core.components import StatsComponent, ResourceComponent, TeamComponent, EffectsComponent
from rpg_core.events import EventBus, DamageEvent, LogEvent, TurnEvent, BattleEndEvent, BaseEvent
from rpg_core.controllers import RandomAIController, BaseController
from rpg_core.engine import BattleEngine
from rpg_core.queries import StatQuery, EffectQuery
from rpg_core.data_loader import DataLoader, get_data_loader

from .protocol import (
    ServerMsgType, ClientMsgType,
    InitStateData, UnitInfo, DamageData, HealData, TurnStartData, BattleEndData,
    EffectInfo, EffectAppliedData, EffectRemovedData, UpdateEffectsData
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
        
        # 战斗中止标志
        self.is_battle_stopped = False
        
        # 当前战斗 ID（用于重开）
        self.current_battle_id: str = "tutorial"
        
        # 订阅事件
        self._subscribe_events()
    
    def stop_battle(self):
        """中止当前战斗"""
        self.is_battle_stopped = True
        if self.engine:
            self.engine.is_battle_over = True
        # 清理控制器
        self.controllers.clear()
        self.ws_controllers.clear()
        self.current_actor = None
    
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
        
        # ECS: 通过组件获取属性
        target_res = target.get(ResourceComponent) if target else None
        target_stats = target.get(StatsComponent) if target else None
        
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
                remaining_hp=target_res.current_hp if target_res else 0,
                max_hp=target_stats.max_hp if target_stats else 0
            ).model_dump()
        }))
        
        # 同时发送 HP 更新
        if target and target_res and target_stats:
            asyncio.create_task(self.send({
                "type": ServerMsgType.UPDATE_HP.value,
                "data": {
                    "unit_id": target.id,
                    "current_hp": target_res.current_hp,
                    "max_hp": target_stats.max_hp
                }
            }))
    
    def _on_heal(self, event: DamageEvent):
        """处理治疗事件"""
        target = self.entities_map.get(event.target_id)
        source = self.entities_map.get(event.source_id)
        
        # ECS: 通过组件获取属性
        target_res = target.get(ResourceComponent) if target else None
        target_stats = target.get(StatsComponent) if target else None
        
        asyncio.create_task(self.send({
            "type": ServerMsgType.HEAL.value,
            "data": HealData(
                source_id=event.source_id,
                source_name=source.name if source else "???",
                target_id=event.target_id,
                target_name=target.name if target else "???",
                amount=event.amount,
                remaining_hp=target_res.current_hp if target_res else 0,
                max_hp=target_stats.max_hp if target_stats else 0
            ).model_dump()
        }))
        
        # 同时发送 HP 更新
        if target and target_res and target_stats:
            asyncio.create_task(self.send({
                "type": ServerMsgType.UPDATE_HP.value,
                "data": {
                    "unit_id": target.id,
                    "current_hp": target_res.current_hp,
                    "max_hp": target_stats.max_hp
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
                        "unit_id": entity.id,
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
    
    async def initialize_battle(self, battle_id: str = "tutorial"):
        """
        初始化战斗
        
        Args:
            battle_id: 战斗配置 ID，对应 data/battles/{battle_id}.json
        """
        # 重置状态
        self.is_battle_stopped = False
        self.current_battle_id = battle_id
        self.controllers.clear()
        self.ws_controllers.clear()
        
        # 使用数据加载器
        loader = get_data_loader()
        
        # 获取战斗配置
        battle_config = loader.get_battle(battle_id)
        if not battle_config:
            print(f"Warning: Battle config '{battle_id}' not found, using default")
            battle_config = {
                "allies": [
                    {"character_id": "hero", "controller": "player"},
                    {"character_id": "mage", "controller": "player"}
                ],
                "enemies": [
                    {"character_id": "dragon", "controller": "ai_random"}
                ]
            }
        
        # 加载技能注册表
        self.skill_registry = loader.get_all_skills()
        
        # 创建友方单位
        allies = []
        for unit_config in battle_config.get("allies", []):
            char_id = unit_config.get("character_id")
            char_template = loader.get_character(char_id)
            
            if not char_template:
                print(f"Warning: Character '{char_id}' not found")
                continue
            
            entity = CombatEntity.create(char_template)
            entity.add(TeamComponent(team="ally"))
            entity.add(EffectsComponent())  # 确保有效果组件
            allies.append(entity)
            
            # 设置控制器
            controller_type = unit_config.get("controller", "player")
            if controller_type == "player":
                ws_ctrl = WebSocketController(self.skill_registry, self.send, entity.id)
                self.controllers[entity.id] = ws_ctrl
                self.ws_controllers[entity.id] = ws_ctrl
            else:
                self.controllers[entity.id] = RandomAIController(self.skill_registry)
        
        # 创建敌方单位
        enemies = []
        for unit_config in battle_config.get("enemies", []):
            char_id = unit_config.get("character_id")
            char_template = loader.get_character(char_id)
            
            if not char_template:
                print(f"Warning: Character '{char_id}' not found")
                continue
            
            entity = CombatEntity.create(char_template)
            entity.add(TeamComponent(team="enemy"))
            entity.add(EffectsComponent())  # 确保有效果组件
            enemies.append(entity)
            
            # 敌人默认使用 AI 控制器
            self.controllers[entity.id] = RandomAIController(self.skill_registry)
        
        # 创建引擎并初始化
        self.engine = BattleEngine(self.bus, self.skill_registry)
        self.engine.initialize(allies=allies, enemies=enemies)
        
        # 发送初始状态
        await self._send_init_state()
    
    async def _send_init_state(self):
        """发送初始状态给前端"""
        # ECS: 通过组件获取属性
        allies_info = []
        for e in self.allies:
            res = e.get(ResourceComponent)
            stats = e.get(StatsComponent)
            allies_info.append(UnitInfo(
                id=e.id,
                name=e.name,
                current_hp=res.current_hp if res else 0,
                max_hp=stats.max_hp if stats else 0,
                current_mp=res.current_mp if res else 0,
                max_mp=stats.max_mp if stats else 0,
                is_dead=e.is_dead,
                team="ally",
                effects=self._get_unit_effects(e)
            ))
        
        enemies_info = []
        for e in self.enemies:
            res = e.get(ResourceComponent)
            stats = e.get(StatsComponent)
            enemies_info.append(UnitInfo(
                id=e.id,
                name=e.name,
                current_hp=res.current_hp if res else 0,
                max_hp=stats.max_hp if stats else 0,
                current_mp=res.current_mp if res else 0,
                max_mp=stats.max_mp if stats else 0,
                is_dead=e.is_dead,
                team="enemy",
                effects=self._get_unit_effects(e)
            ))
        
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
        
        while not self.engine.is_battle_over and not self.is_battle_stopped:
            self.engine.increment_turn()
            
            # 复用引擎的排序逻辑
            units = self.engine.get_turn_order()
            
            if not units:
                break
            
            for unit in units:
                if self.engine.is_battle_over or self.is_battle_stopped:
                    break
                if unit.is_dead:
                    continue
                
                self.current_actor = unit
                
                # 1. 引擎准备：回合开始结算，获取上下文
                context = self.engine.start_turn(unit)
                
                # 检查 DOT 效果是否导致死亡
                if unit.is_dead:
                    self.bus.publish(LogEvent(message=f"{unit.name} 因持续伤害而倒下了！"))
                    if self.engine.check_battle_end():
                        break
                    continue
                
                # 检查眩晕状态 - 跳过行动
                if EffectQuery.is_stunned(unit):
                    self.bus.publish(LogEvent(message=f"{unit.name} 处于眩晕状态，无法行动！"))
                    await asyncio.sleep(0.3)
                    continue
                
                # 2. 获取输入（异步等待！）
                # ECS: 使用 entity.id 作为控制器 key
                controller = self.controllers.get(unit.id)
                if not controller:
                    continue
                
                if isinstance(controller, WebSocketController):
                    # 等待前端发包
                    action = await controller.select_action_async(context)
                    # 检查是否被中止
                    if self.is_battle_stopped:
                        break
                else:
                    # AI 仍然是同步的
                    action = controller.select_action(context)
                
                # 3. 引擎执行（纯计算，即便在异步函数里调用同步函数也是安全的）
                self.engine.resolve_action(unit, action, context)
                
                # 发送 MP 更新（技能消耗后）
                await self._send_mp_update(unit)
                
                # 发送所有单位的效果状态更新
                await self._send_effects_update_all()
                
                # 4. 检查结束
                if self.engine.check_battle_end():
                    break
                
                # 给前端一点时间处理动画
                await asyncio.sleep(0.3)
    
    def _get_unit_effects(self, unit: CombatEntity) -> List[EffectInfo]:
        """获取单位当前的所有效果信息"""
        effects_comp = unit.get(EffectsComponent)
        if not effects_comp:
            return []
        
        effect_infos = []
        for effect in effects_comp.effects:
            effect_infos.append(EffectInfo(
                name=effect.name,
                description=effect.description,
                duration=effect.duration,
                is_buff=effect.is_buff,
                stacks=getattr(effect, 'current_stacks', 1),
                icon=self._get_effect_icon(effect)
            ))
        return effect_infos
    
    def _get_effect_icon(self, effect) -> str:
        """根据效果类型返回图标"""
        effect_icons = {
            "中毒": "🟢",
            "燃烧": "🔥",
            "狂暴": "💢",
            "防御强化": "🛡️",
            "再生": "💚",
            "虚弱": "📉",
            "无敌": "✨",
            "眩晕": "💫",
            "沉默": "🔇",
        }
        return effect_icons.get(effect.name, "⭐")
    
    async def _send_effects_update(self, unit: CombatEntity):
        """发送单个单位的效果状态更新"""
        await self.send({
            "type": ServerMsgType.UPDATE_EFFECTS.value,
            "data": UpdateEffectsData(
                unit_id=unit.id,
                effects=self._get_unit_effects(unit)
            ).model_dump()
        })
    
    async def _send_effects_update_all(self):
        """发送所有单位的效果状态更新"""
        for unit in list(self.allies) + list(self.enemies):
            if not unit.is_dead:
                await self._send_effects_update(unit)
    
    async def _send_mp_update(self, unit: CombatEntity):
        """发送 MP 更新给前端"""
        # ECS: 通过组件获取属性
        res = unit.get(ResourceComponent)
        stats = unit.get(StatsComponent)
        
        await self.send({
            "type": ServerMsgType.UPDATE_MP.value,
            "data": {
                "unit_id": unit.id,
                "current_mp": res.current_mp if res else 0,
                "max_mp": stats.max_mp if stats else 0
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
                # ECS: 使用 entity.id 作为控制器 key
                ctrl = self.ws_controllers.get(self.current_actor.id)
                if ctrl:
                    ctrl.receive_client_message(msg_type, data)
