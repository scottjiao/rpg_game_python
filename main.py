import time
from rpg_core.enums import TargetType, DamageType, EventType, SkillCategory
from rpg_core.models import CharacterTemplate, SkillTemplate, CombatEntity, BattleStats
from rpg_core.events import EventBus, DamageEvent, LogEvent, BattleEndEvent
from rpg_core.controllers import RandomAIController, HumanCLIController
from rpg_core.engine import BattleEngine

# --- 1. 简易 UI (Logger) ---
class ConsoleUI:
    def __init__(self, bus: EventBus, entities_map):
        self.entities = entities_map
        bus.subscribe(EventType.LOG, self.on_log)
        bus.subscribe(EventType.DAMAGE_DEALT, self.on_damage)
        bus.subscribe(EventType.HEAL_DEALT, self.on_heal)
        bus.subscribe(EventType.TURN_START, self.on_turn)
        bus.subscribe(EventType.UNIT_DEATH, self.on_death)
        bus.subscribe(EventType.BATTLE_END, self.on_end)

    def _name(self, uid):
        return self.entities[uid].name

    def on_log(self, event: LogEvent):
        print(f"[SYS] {event.message}")

    def on_turn(self, event):
        print(f"\n>>> 第 {event.turn_number} 回合: 轮到 {event.actor_name} <<<")

    def on_damage(self, event: DamageEvent):
        tgt = self._name(event.target_id)
        src = self._name(event.source_id)
        crit = " (暴击!)" if event.is_crit else ""
        print(f"⚔️  {src} 对 {tgt} 造成了 {event.amount} 点 {event.damage_type} 伤害{crit}!")
        
        # 显示剩余血量
        target_entity = self.entities[event.target_id]
        print(f"    └── {tgt} HP: {target_entity.current_hp}/{target_entity.stats.max_hp}")

    def on_heal(self, event: DamageEvent):
        tgt = self._name(event.target_id)
        src = self._name(event.source_id)
        print(f"💚 {src} 治疗了 {tgt} {event.amount} 点生命!")

    def on_death(self, event):
        # 这里的 event 只有 type，为了简化没传谁死了，实际可以传
        print("💀 有单位倒下了！")

    def on_end(self, event: BattleEndEvent):
        print(f"\n🏆 战斗结束！获胜方: {event.winner_team}")

# --- 2. 数据构造 (Mock JSON loading) ---
def create_mock_data():
    # Skills - 注意 category 字段区分攻击技能和法术
    skills = [
        SkillTemplate(
            id="fireball", name="火球术",
            category=SkillCategory.MAGIC,  # 法术
            cost_mp=10, cooldown=0,
            target_type=TargetType.SINGLE_ENEMY, 
            damage_type=DamageType.MAGICAL, power_coef=2.5
        ),
        SkillTemplate(
            id="heal", name="次级治疗",
            category=SkillCategory.MAGIC,  # 法术
            cost_mp=15, cooldown=2,
            target_type=TargetType.SINGLE_ALLY, 
            damage_type=DamageType.HEAL, power_coef=3.0
        ),
        SkillTemplate(
            id="slash", name="旋风斩",
            category=SkillCategory.ATTACK,  # 攻击类技能
            cost_mp=20, cooldown=3,
            target_type=TargetType.ALL_ENEMIES, 
            damage_type=DamageType.PHYSICAL, power_coef=0.8
        ),
        SkillTemplate(
            id="power_strike", name="强力攻击",
            category=SkillCategory.ATTACK,  # 攻击类技能
            cost_mp=5, cooldown=0,
            target_type=TargetType.SINGLE_ENEMY,
            damage_type=DamageType.PHYSICAL, power_coef=1.5
        ),
    ]
    skill_registry = {s.id: s for s in skills}

    # Characters
    hero_stats = BattleStats(max_hp=200, max_mp=50, max_san=100, atk=20, matk=10, spd=12, acc=1.2, crit=0.2, def_=5)
    hero_tmpl = CharacterTemplate(id="hero", name="勇者", base_stats=hero_stats, skill_ids=["slash", "power_strike", "heal"])

    mage_stats = BattleStats(max_hp=120, max_mp=100, max_san=80, atk=5, matk=30, spd=10, acc=1.0, crit=0.3, def_=2)
    mage_tmpl = CharacterTemplate(id="mage", name="法师", base_stats=mage_stats, skill_ids=["fireball", "heal"])

    boss_stats = BattleStats(max_hp=600, max_mp=999, atk=25, matk=10, spd=8, acc=0.9, def_=8, mdef=5)
    boss_tmpl = CharacterTemplate(id="dragon", name="恶龙", base_stats=boss_stats, skill_ids=["fireball"])

    return skill_registry, hero_tmpl, mage_tmpl, boss_tmpl

# --- 3. Main Entry ---
if __name__ == "__main__":
    # 初始化
    bus = EventBus()
    skill_registry, hero_tmpl, mage_tmpl, boss_tmpl = create_mock_data()
    
    # 创建实体
    hero = CombatEntity.create(hero_tmpl)
    mage = CombatEntity.create(mage_tmpl)
    boss = CombatEntity.create(boss_tmpl)
    
    # 建立 ID 索引方便 UI 查名字
    entities_map = {e.instance_id: e for e in [hero, mage, boss]}

    # 启动 UI 监听
    ui = ConsoleUI(bus, entities_map)

    # 配置 AI  
    controllers = {
        hero.instance_id: HumanCLIController(skill_registry),
        mage.instance_id: HumanCLIController(skill_registry),
        boss.instance_id: RandomAIController(skill_registry)
    }

    # 启动引擎
    engine = BattleEngine(bus, skill_registry)
    engine.initialize(
        allies=[hero, mage],
        enemies=[boss],
        controllers=controllers
    )
    
    engine.run_battle_loop()