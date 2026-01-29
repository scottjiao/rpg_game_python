"""
data_loader.py - 数据加载器

负责从 JSON 文件加载游戏数据，并转换为运行时对象。

支持加载：
- 技能模板 (skills.json)
- 角色模板 (characters.json)
- 战斗配置 (battles/*.json)

设计原则：
- 数据与逻辑分离
- JSON 存放数值配置，Python 处理复杂逻辑
- 支持热加载（可选）
"""
import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

from .models import SkillTemplate, CharacterTemplate, BattleStats
from .enums import SkillCategory, TargetType, DamageType


class DataLoader:
    """
    游戏数据加载器
    
    用法：
        loader = DataLoader("backend/data")
        loader.load_all()
        
        skill = loader.get_skill("fireball")
        character = loader.get_character("hero")
        battle = loader.get_battle("tutorial")
    """
    
    def __init__(self, data_dir: str = None):
        """
        Args:
            data_dir: 数据目录路径，默认为 backend/data
        """
        if data_dir is None:
            # 默认路径：相对于此文件的位置
            data_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "data"
            )
        
        self.data_dir = Path(data_dir)
        
        # 缓存已加载的数据
        self._skills: Dict[str, SkillTemplate] = {}
        self._characters: Dict[str, CharacterTemplate] = {}
        self._battles: Dict[str, dict] = {}
        
        # 原始 JSON 数据（用于调试和扩展）
        self._raw_skills: Dict[str, dict] = {}
        self._raw_characters: Dict[str, dict] = {}
    
    def load_all(self):
        """加载所有数据文件"""
        self.load_skills()
        self.load_characters()
        self.load_battles()
    
    # ==================== 技能加载 ====================
    
    def load_skills(self) -> Dict[str, SkillTemplate]:
        """
        加载技能数据
        
        Returns:
            技能模板字典 {skill_id: SkillTemplate}
        """
        skills_file = self.data_dir / "skills.json"
        
        if not skills_file.exists():
            print(f"Warning: Skills file not found at {skills_file}")
            return {}
        
        with open(skills_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        
        self._raw_skills = raw_data
        self._skills = {}
        
        for skill_id, data in raw_data.items():
            try:
                template = self._parse_skill(skill_id, data)
                self._skills[skill_id] = template
            except Exception as e:
                print(f"Error loading skill '{skill_id}': {e}")
        
        print(f"Loaded {len(self._skills)} skills")
        return self._skills
    
    def _parse_skill(self, skill_id: str, data: dict) -> SkillTemplate:
        """解析单个技能数据"""
        return SkillTemplate(
            id=skill_id,
            name=data.get("name", skill_id),
            description=data.get("description", ""),
            category=SkillCategory(data.get("category", "ATTACK")),
            cost_mp=data.get("cost_mp", 0),
            cost_san=data.get("cost_san", 0),
            cooldown=data.get("cooldown", 0),
            target_type=TargetType(data.get("target_type", "SINGLE_ENEMY")),
            damage_type=DamageType(data.get("damage_type", "PHYSICAL")),
            power_coef=data.get("power_coef", 1.0),
            fixed_value=data.get("fixed_value", 0),
        )
    
    def get_skill(self, skill_id: str) -> Optional[SkillTemplate]:
        """获取技能模板"""
        return self._skills.get(skill_id)
    
    def get_skill_effects(self, skill_id: str) -> tuple:
        """
        获取技能的效果配置
        
        Returns:
            (effect_ids, effect_params) 元组
        """
        raw = self._raw_skills.get(skill_id, {})
        effect_ids = raw.get("effect_ids", [])
        effect_params = raw.get("effect_params", {})
        return effect_ids, effect_params
    
    def get_all_skills(self) -> Dict[str, SkillTemplate]:
        """获取所有技能模板"""
        return self._skills.copy()
    
    # ==================== 角色加载 ====================
    
    def load_characters(self) -> Dict[str, CharacterTemplate]:
        """
        加载角色数据
        
        Returns:
            角色模板字典 {character_id: CharacterTemplate}
        """
        chars_file = self.data_dir / "characters.json"
        
        if not chars_file.exists():
            print(f"Warning: Characters file not found at {chars_file}")
            return {}
        
        with open(chars_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        
        self._raw_characters = raw_data
        self._characters = {}
        
        for char_id, data in raw_data.items():
            try:
                template = self._parse_character(char_id, data)
                self._characters[char_id] = template
            except Exception as e:
                print(f"Error loading character '{char_id}': {e}")
        
        print(f"Loaded {len(self._characters)} characters")
        return self._characters
    
    def _parse_character(self, char_id: str, data: dict) -> CharacterTemplate:
        """解析单个角色数据"""
        stats_data = data.get("base_stats", {})
        
        # 处理 def 关键字冲突
        if "def" in stats_data:
            stats_data["def_"] = stats_data.pop("def")
        
        base_stats = BattleStats(**stats_data)
        
        return CharacterTemplate(
            id=char_id,
            name=data.get("name", char_id),
            base_stats=base_stats,
            skill_ids=data.get("skill_ids", []),
        )
    
    def get_character(self, char_id: str) -> Optional[CharacterTemplate]:
        """获取角色模板"""
        return self._characters.get(char_id)
    
    def get_all_characters(self) -> Dict[str, CharacterTemplate]:
        """获取所有角色模板"""
        return self._characters.copy()
    
    # ==================== 战斗配置加载 ====================
    
    def load_battles(self) -> Dict[str, dict]:
        """
        加载所有战斗配置
        
        Returns:
            战斗配置字典 {battle_id: config}
        """
        battles_dir = self.data_dir / "battles"
        
        if not battles_dir.exists():
            print(f"Warning: Battles directory not found at {battles_dir}")
            return {}
        
        self._battles = {}
        
        for battle_file in battles_dir.glob("*.json"):
            try:
                with open(battle_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                battle_id = data.get("id", battle_file.stem)
                self._battles[battle_id] = data
            except Exception as e:
                print(f"Error loading battle '{battle_file}': {e}")
        
        print(f"Loaded {len(self._battles)} battle configs")
        return self._battles
    
    def get_battle(self, battle_id: str) -> Optional[dict]:
        """获取战斗配置"""
        return self._battles.get(battle_id)
    
    def get_all_battles(self) -> Dict[str, dict]:
        """获取所有战斗配置"""
        return self._battles.copy()
    
    def list_battle_ids(self) -> List[str]:
        """列出所有战斗配置 ID"""
        return list(self._battles.keys())


# ============================================================
# 全局单例（可选）
# ============================================================

_default_loader: Optional[DataLoader] = None


def get_data_loader() -> DataLoader:
    """
    获取全局数据加载器实例
    
    首次调用会自动加载所有数据
    """
    global _default_loader
    
    if _default_loader is None:
        _default_loader = DataLoader()
        _default_loader.load_all()
    
    return _default_loader


def reload_data():
    """重新加载所有数据（热加载）"""
    global _default_loader
    
    if _default_loader is None:
        _default_loader = DataLoader()
    
    _default_loader.load_all()
    return _default_loader
