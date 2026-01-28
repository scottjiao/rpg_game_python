from typing import List, Callable, Dict, Any
from collections import defaultdict
from pydantic import BaseModel
from .enums import EventType

# --- 事件数据包 (Payloads) ---

class BaseEvent(BaseModel):
    type: EventType

class LogEvent(BaseEvent):
    type: EventType = EventType.LOG
    message: str

class TurnEvent(BaseEvent):
    type: EventType = EventType.TURN_START # or TURN_END
    turn_number: int
    actor_id: str
    actor_name: str

class DamageEvent(BaseEvent):
    type: EventType = EventType.DAMAGE_DEALT
    source_id: str
    target_id: str
    amount: int
    is_crit: bool
    damage_type: str

class BattleEndEvent(BaseEvent):
    type: EventType = EventType.BATTLE_END
    winner_team: str # "ALLIES" or "ENEMIES"

# --- 同步事件总线 ---

class EventBus:
    def __init__(self):
        # Key: 事件类型, Value: 回调函数列表
        self._subscribers: Dict[EventType, List[Callable[[BaseModel], None]]] = defaultdict(list)

    def subscribe(self, event_type: EventType, callback: Callable[[BaseModel], None]):
        """
        订阅事件。
        callback: 必须是一个接受 BaseEvent (或其子类) 的函数。
        """
        self._subscribers[event_type].append(callback)

    def publish(self, event: BaseEvent):
        """
        同步广播事件。所有监听器会按顺序立即执行。
        这确保了日志输出和逻辑执行的顺序一致性。
        """
        if event.type in self._subscribers:
            for callback in self._subscribers[event.type]:
                callback(event)