"""
websocket_controller.py - WebSocket 异步控制器

替代 HumanCLIController，通过 WebSocket 与前端交互。
使用 asyncio.Future 实现异步等待玩家输入。
"""
import asyncio
from typing import Dict, List, Optional, Any
from rpg_core.controllers import BaseController
from rpg_core.models import BattleContext, CombatAction, SkillTemplate, CombatEntity
from rpg_core.logic import ActionGenerator
from rpg_core.enums import ActionCategory, SkillCategory
from .protocol import (
    ServerMessage, ServerMsgType, ClientMsgType,
    RequestActionData, RequestSkillData, RequestTargetData,
    CategoryOption, SkillInfo, TargetOption
)


class WebSocketController(BaseController):
    """
    WebSocket 控制器：通过网络与前端交互
    
    工作流程：
    1. 发送 REQUEST_ACTION 消息给前端
    2. 等待前端的 SELECT_CATEGORY 响应
    3. 发送 REQUEST_SKILL 消息
    4. 等待 SELECT_SKILL 响应
    5. 发送 REQUEST_TARGET 消消息
    6. 等待 SELECT_TARGET 响应
    7. 返回最终的 CombatAction
    """
    
    CATEGORY_NAMES = {
        ActionCategory.ATTACK: "攻击",
        ActionCategory.MAGIC: "法术",
        ActionCategory.DEFEND: "防御",
        ActionCategory.ITEM: "物品",
        ActionCategory.FLEE: "逃跑",
    }
    
    def __init__(self, skill_registry: Dict[str, SkillTemplate], send_func, actor_id: str):
        """
        Args:
            skill_registry: 技能注册表
            send_func: 异步发送消息的函数 async def send(msg: dict)
            actor_id: 该控制器负责的角色 ID
        """
        self.skill_registry = skill_registry
        self.generator = ActionGenerator(skill_registry)
        self.send = send_func
        self.actor_id = actor_id
        
        # 用于等待客户端响应的 Future
        self._pending_response: Optional[asyncio.Future] = None
    
    def receive_client_message(self, msg_type: ClientMsgType, data: Dict[str, Any]):
        """
        接收来自客户端的消息，解除 Future 阻塞
        """
        if self._pending_response and not self._pending_response.done():
            self._pending_response.set_result((msg_type, data))
    
    async def _wait_for_response(self, *expected_types: ClientMsgType):
        """
        等待客户端响应
        """
        loop = asyncio.get_event_loop()
        
        while True:
            # 创建 Future 等待下一次消息
            self._pending_response = loop.create_future()
            
            try:
                msg_type, data = await self._pending_response
            finally:
                self._pending_response = None
            
            # 如果是期望的消息类型，则返回
            if msg_type in expected_types:
                return msg_type, data
            
            # 如果不是期望的消息（可能是上一步的点击残留，或者乱序到达的消息），则忽略并继续等待
            print(f"Warning: Ignored unexpected message type: {msg_type}, expected: {expected_types}")
    
    # ==================== 重写 BaseController ====================
    
    def select_action(self, context: BattleContext) -> CombatAction:
        """
        同步接口（兼容原有 Engine）
        注意：这里不能直接 await，需要在外部用 asyncio 调度
        """
        raise NotImplementedError("Use select_action_async instead")
    
    async def select_action_async(self, context: BattleContext) -> CombatAction:
        """
        异步版本的 select_action
        """
        actor = context.current_actor
        
        while True:
            # Step 1: 选择行为大类
            category = await self._step1_select_category(actor, context)
            
            if category == ActionCategory.DEFEND:
                return self.generator.build_action(actor, category, None, [])
            
            # Step 2: 选择具体技能
            result = await self._step2_select_skill(actor, category, context)
            if result == "BACK":
                continue
            skill = result
            
            # Step 3: 选择目标
            targets = await self._step3_select_targets(actor, skill, context)
            if targets == "BACK":
                continue
            
            return self.generator.build_action(actor, category, skill, targets)
    
    async def _step1_select_category(
        self, actor: CombatEntity, context: BattleContext
    ) -> ActionCategory:
        """第一步：发送可用类别，等待选择"""
        categories = self.generator.get_available_categories(actor, context)
        
        # 构造选项
        options = [
            CategoryOption(id=cat.value, name=self.CATEGORY_NAMES.get(cat, cat.value))
            for cat in categories
        ]
        
        # 发送请求
        await self.send({
            "type": ServerMsgType.REQUEST_ACTION.value,
            "data": RequestActionData(
                actor_id=actor.instance_id,
                actor_name=actor.name,
                categories=options
            ).model_dump()
        })
        
        # 等待响应
        _, data = await self._wait_for_response(ClientMsgType.SELECT_CATEGORY)
        selected_id = data.get("category_id")
        
        for cat in categories:
            if cat.value == selected_id:
                return cat
        
        # 默认防御
        return ActionCategory.DEFEND
    
    async def _step2_select_skill(
        self, actor: CombatEntity, category: ActionCategory, context: BattleContext
    ):
        """第二步：发送可用技能，等待选择"""
        skills = self.generator.get_available_skills(actor, category, context)
        has_basic_attack = (category == ActionCategory.ATTACK)
        
        # 构造技能信息
        skill_infos = []
        for sk in skills:
            # 判断技能是否可用
            is_usable = True
            reason = ""
            
            # 检查冷却
            if actor.cooldowns.get(sk.id, 0) > 0:
                is_usable = False
                reason = "冷却中"
            # 检查蓝量
            elif actor.current_mp < sk.cost_mp:
                is_usable = False
                reason = "MP不足"
            # 检查san值
            elif actor.current_san < sk.cost_san:
                is_usable = False
                reason = "SAN不足"

            skill_infos.append(SkillInfo(
                id=sk.id,
                name=sk.name,
                cost_mp=sk.cost_mp,
                cost_san=sk.cost_san,
                cooldown=sk.cooldown,
                current_cd=actor.cooldowns.get(sk.id, 0),
                description=sk.description,
                is_usable=is_usable,
                unusable_reason=reason
            ))
        
        # 发送请求
        await self.send({
            "type": ServerMsgType.REQUEST_SKILL.value,
            "data": RequestSkillData(
                actor_id=actor.instance_id,
                category=category.value,
                category_name=self.CATEGORY_NAMES.get(category, category.value),
                has_basic_attack=has_basic_attack,
                skills=skill_infos
            ).model_dump()
        })
        
        # 等待响应
        _, data = await self._wait_for_response(ClientMsgType.SELECT_SKILL)
        
        if data.get("back"):
            return "BACK"
        
        skill_id = data.get("skill_id")
        
        if skill_id is None:
            return None  # 普攻
        
        # 获取技能并校验是否可用
        skill = self.skill_registry.get(skill_id)
        if skill:
            # 校验冷却
            if actor.cooldowns.get(skill.id, 0) > 0:
                # 技能冷却中，重新请求选择
                await self.send({
                    "type": ServerMsgType.LOG.value,
                    "data": {"message": f"技能 {skill.name} 正在冷却中，请选择其他技能！"}
                })
                return await self._step2_select_skill(actor, category, context)
            # 校验 MP
            if actor.current_mp < skill.cost_mp:
                await self.send({
                    "type": ServerMsgType.LOG.value,
                    "data": {"message": f"MP 不足，无法使用 {skill.name}！"}
                })
                return await self._step2_select_skill(actor, category, context)
            # 校验 SAN
            if actor.current_san < skill.cost_san:
                await self.send({
                    "type": ServerMsgType.LOG.value,
                    "data": {"message": f"SAN 不足，无法使用 {skill.name}！"}
                })
                return await self._step2_select_skill(actor, category, context)
        
        return skill
    
    async def _step3_select_targets(
        self, actor: CombatEntity, skill: Optional[SkillTemplate], context: BattleContext
    ):
        """第三步：发送可选目标，等待选择"""
        targets = self.generator.get_valid_targets(actor, skill, context)
        is_aoe = self.generator.is_aoe(skill)
        skill_name = skill.name if skill else "普通攻击"
        
        # 构造目标选项
        target_options = [
            TargetOption(
                id=t.instance_id,
                name=t.name,
                current_hp=t.current_hp,
                max_hp=t.stats.max_hp
            )
            for t in targets
        ]
        
        # 发送请求
        await self.send({
            "type": ServerMsgType.REQUEST_TARGET.value,
            "data": RequestTargetData(
                actor_id=actor.instance_id,
                skill_id=skill.id if skill else None,
                skill_name=skill_name,
                is_aoe=is_aoe,
                targets=target_options
            ).model_dump()
        })
        
        # 等待响应
        _, data = await self._wait_for_response(ClientMsgType.SELECT_TARGET)
        
        if data.get("back"):
            return "BACK"
        
        target_ids = data.get("target_ids", [])
        
        # 如果是群体技能，返回所有目标
        if is_aoe:
            return targets
        
        # 单体技能，返回选中的目标
        return [t for t in targets if t.instance_id in target_ids]
