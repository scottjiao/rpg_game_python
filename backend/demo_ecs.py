"""
demo_ecs.py - ECS 架构演示

这个 demo 展示了新 ECS 架构的核心功能：
1. 创建实体并添加组件
2. 使用 StatQuery 获取 Buff 修正后的属性
3. 使用 EffectSystem 添加/处理效果
4. 展示 Effect 如何修正属性和触发回合效果
"""
import sys
import os

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rpg_core.entity import Entity, CombatEntity, EntityFactory
from rpg_core.components import (
    IdentityComponent,
    StatsComponent,
    ResourceComponent,
    CombatStateComponent,
    EffectsComponent,
    SkillsComponent,
)
from rpg_core.effects import (
    PoisonEffect,
    RageEffect,
    DefenseUpEffect,
    InvincibleEffect,
    RegenEffect,
)
from rpg_core.systems import EffectSystem, ResourceSystem, CooldownSystem
from rpg_core.queries import StatQuery, ResourceQuery, EffectQuery
from rpg_core.events import EventBus, LogEvent, EventType


def print_separator(title: str = ""):
    print("\n" + "=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def print_entity_status(entity: Entity, label: str = ""):
    """打印实体状态"""
    res = entity.get(ResourceComponent)
    stats = entity.get(StatsComponent)
    
    print(f"\n【{label or entity.name}】")
    print(f"  HP: {res.current_hp}/{stats.max_hp}")
    print(f"  MP: {res.current_mp}/{stats.max_mp}")
    
    # 显示基础属性 vs 修正后属性
    base_atk = stats.atk
    effective_atk = StatQuery.get_int(entity, "atk")
    base_def = stats.def_
    effective_def = StatQuery.get_int(entity, "def_")
    
    print(f"  ATK: {base_atk}", end="")
    if effective_atk != base_atk:
        print(f" → {effective_atk} (Buff修正)", end="")
    print()
    
    print(f"  DEF: {base_def}", end="")
    if effective_def != base_def:
        print(f" → {effective_def} (Buff修正)", end="")
    print()
    
    # 显示效果
    effects = EffectQuery.get_all_effects(entity)
    if effects:
        print(f"  效果: ", end="")
        effect_strs = [f"{e.name}({e.duration}回合)" for e in effects]
        print(", ".join(effect_strs))


def demo_basic_entity():
    """演示：基础实体创建"""
    print_separator("Demo 1: 基础实体创建")
    
    # 方式1：手动创建实体并添加组件
    hero = Entity()
    hero.add(IdentityComponent(name="勇者", template_id="hero"))
    hero.add(StatsComponent(max_hp=200, max_mp=50, atk=20, def_=10, spd=12))
    hero.add(ResourceComponent(current_hp=200, current_mp=50, current_san=100))
    hero.add(CombatStateComponent())
    hero.add(EffectsComponent())
    
    print(f"创建实体: {hero.name} (ID: {hero.id[:8]}...)")
    print(f"  - 拥有 {len(hero.components)} 个组件")
    print(f"  - ATK = {StatQuery.get_int(hero, 'atk')}")
    print(f"  - HP = {ResourceQuery.get_hp(hero)}/{StatQuery.get_int(hero, 'max_hp')}")
    
    # 方式2：使用工厂方法
    print("\n使用 EntityFactory 创建:")
    mage = EntityFactory.create_combat_entity(
        name="法师",
        template_id="mage",
        stats=StatsComponent(max_hp=120, max_mp=100, atk=5, matk=30, def_=5, spd=10),
        skill_ids=["fireball", "heal"],
        team="ally"
    )
    print(f"创建实体: {mage.name}")
    print(f"  - HP = {ResourceQuery.get_hp(mage)}/{StatQuery.get_int(mage, 'max_hp')}")
    print(f"  - MATK = {StatQuery.get_int(mage, 'matk')}")


def demo_buff_system():
    """演示：Buff 系统和属性修正"""
    print_separator("Demo 2: Buff 系统和属性修正")
    
    # 创建一个战士
    warrior = Entity()
    warrior.add(IdentityComponent(name="战士", template_id="warrior"))
    warrior.add(StatsComponent(max_hp=300, max_mp=30, atk=25, def_=15, spd=8))
    warrior.add(ResourceComponent(current_hp=300, current_mp=30, current_san=100))
    warrior.add(CombatStateComponent())
    warrior.add(EffectsComponent())
    
    # 创建事件总线（用于日志）
    bus = EventBus()
    bus.subscribe(EventType.LOG, lambda e: print(f"  [LOG] {e.message}"))
    
    print("初始状态:")
    print_entity_status(warrior)
    
    # 添加狂暴效果 (ATK +50%)
    print("\n>>> 添加「狂暴」效果 (ATK +50%, 持续3回合)")
    rage = RageEffect(duration=3, atk_bonus=0.5)
    EffectSystem.add_effect(warrior, rage, bus)
    print_entity_status(warrior)
    
    # 添加防御强化 (DEF +30%)
    print("\n>>> 添加「防御强化」效果 (DEF +30%, 持续2回合)")
    defense_up = DefenseUpEffect(duration=2, def_bonus=0.3)
    EffectSystem.add_effect(warrior, defense_up, bus)
    print_entity_status(warrior)
    
    # 模拟回合流逝
    print("\n>>> 模拟回合结束，触发效果 tick")
    context = {"bus": bus}
    EffectSystem.tick_effects(warrior, "TURN_END", context)
    print_entity_status(warrior)
    
    print("\n>>> 再过一回合...")
    EffectSystem.tick_effects(warrior, "TURN_END", context)
    print_entity_status(warrior)
    
    print("\n>>> 再过一回合...")
    EffectSystem.tick_effects(warrior, "TURN_END", context)
    print_entity_status(warrior)


def demo_dot_effects():
    """演示：DoT (伤害/治疗 over time) 效果"""
    print_separator("Demo 3: DoT 效果 (中毒 & 再生)")
    
    # 创建目标
    target = Entity()
    target.add(IdentityComponent(name="测试目标", template_id="dummy"))
    target.add(StatsComponent(max_hp=100, max_mp=50, atk=10, def_=5))
    target.add(ResourceComponent(current_hp=80, current_mp=50, current_san=100))
    target.add(CombatStateComponent())
    target.add(EffectsComponent())
    
    bus = EventBus()
    bus.subscribe(EventType.LOG, lambda e: print(f"  [LOG] {e.message}"))
    context = {"bus": bus}
    
    print("初始状态:")
    print_entity_status(target)
    
    # 添加中毒效果
    print("\n>>> 添加「中毒」效果 (每回合 -15 HP, 持续3回合)")
    poison = PoisonEffect(duration=3, damage_per_turn=15)
    EffectSystem.add_effect(target, poison, bus)
    
    # 添加再生效果
    print(">>> 添加「再生」效果 (每回合 +10 HP, 持续5回合)")
    regen = RegenEffect(duration=5, heal_per_turn=10)
    EffectSystem.add_effect(target, regen, bus)
    
    print_entity_status(target)
    
    # 模拟多个回合
    for turn in range(1, 6):
        print(f"\n--- 回合 {turn} 开始 ---")
        EffectSystem.tick_effects(target, "TURN_START", context)
        print_entity_status(target)


def demo_invincible():
    """演示：无敌效果"""
    print_separator("Demo 4: 无敌效果")
    
    # 创建目标
    hero = Entity()
    hero.add(IdentityComponent(name="勇者", template_id="hero"))
    hero.add(StatsComponent(max_hp=200, max_mp=50, atk=20, def_=10))
    hero.add(ResourceComponent(current_hp=200, current_mp=50, current_san=100))
    hero.add(CombatStateComponent())
    hero.add(EffectsComponent())
    
    bus = EventBus()
    bus.subscribe(EventType.LOG, lambda e: print(f"  [LOG] {e.message}"))
    
    print("初始状态:")
    print(f"  HP: {ResourceQuery.get_hp(hero)}")
    print(f"  受伤修正系数: {StatQuery.get_damage_received_modifier(hero)}")
    
    # 尝试造成伤害
    print("\n>>> 受到 50 点伤害")
    actual = ResourceSystem.deal_damage(hero, 50, bus)
    print(f"  实际伤害: {actual}")
    print(f"  HP: {ResourceQuery.get_hp(hero)}")
    
    # 添加无敌效果
    print("\n>>> 添加「无敌」效果 (持续2回合)")
    invincible = InvincibleEffect(duration=2)
    EffectSystem.add_effect(hero, invincible, bus)
    print(f"  受伤修正系数: {StatQuery.get_damage_received_modifier(hero)}")
    
    # 再次尝试造成伤害
    print("\n>>> 再次受到 50 点伤害")
    actual = ResourceSystem.deal_damage(hero, 50, bus)
    print(f"  实际伤害: {actual}")
    print(f"  HP: {ResourceQuery.get_hp(hero)}")


def demo_combat_entity_compat():
    """演示：CombatEntity 向后兼容"""
    print_separator("Demo 5: CombatEntity 向后兼容")
    
    from rpg_core.models import CharacterTemplate, BattleStats
    
    # 使用旧的模板创建方式
    template = CharacterTemplate(
        id="hero",
        name="勇者",
        base_stats=BattleStats(max_hp=200, max_mp=50, atk=20, def_=10, spd=12),
        skill_ids=["slash", "heal"]
    )
    
    # 使用 CombatEntity.create() 保持向后兼容
    hero = CombatEntity.create(template)
    
    print(f"使用 CharacterTemplate 创建 CombatEntity:")
    print(f"  name: {hero.name}")
    print(f"  instance_id: {hero.instance_id[:8]}...")  # 兼容旧属性名
    print(f"  current_hp: {hero.current_hp}")  # 兼容旧属性访问
    print(f"  stats.atk: {hero.stats.atk}")  # 兼容旧属性访问
    print(f"  known_skill_ids: {hero.known_skill_ids}")
    
    # 同时也支持新的 ECS 访问方式
    print(f"\n同时支持 ECS 访问方式:")
    print(f"  entity.id: {hero.id[:8]}...")
    print(f"  StatQuery.get(hero, 'atk'): {StatQuery.get_int(hero, 'atk')}")
    print(f"  ResourceQuery.get_hp(hero): {ResourceQuery.get_hp(hero)}")


def main():
    print("\n" + "=" * 60)
    print("   RPG 战斗系统 - ECS 架构演示")
    print("=" * 60)
    
    demo_basic_entity()
    demo_buff_system()
    demo_dot_effects()
    demo_invincible()
    demo_combat_entity_compat()
    
    print_separator("演示结束")
    print("\nECS 架构的优势:")
    print("1. 组合优于继承 - 通过添加/移除组件改变实体行为")
    print("2. 属性动态修正 - Buff 通过 Effect.modify_stat() 自动生效")
    print("3. 解耦的逻辑 - System 处理逻辑，Entity 只是数据容器")
    print("4. 易于扩展 - 添加新效果只需创建新的 Effect 子类")
    print("5. 向后兼容 - CombatEntity 保留旧 API，渐进式迁移")


if __name__ == "__main__":
    main()
