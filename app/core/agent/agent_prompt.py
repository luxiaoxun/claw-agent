# core/agent/agent_prompt.py
from typing import List, Dict, Any, Optional
from core.skill.skill_manager import SkillManager
from config.logging_config import get_logger
from config.settings import WORKSPACE_DIR

logger = get_logger(__name__)


class AgentPrompt:
    """
    Agent 提示词管理器
    """

    def __init__(self):
        """
        初始化提示词管理器
        """
        self.skill_manager = SkillManager.get_instance()
        self.system_prompt: Optional[str] = None
        self._last_skill_hash: int = 0

    def _get_skill_hash(self) -> int:
        """获取当前skills的hash值，用于检测变化"""
        # 收集所有skill的name和description
        skill_items = []
        for name, metadata in self.skill_manager.skills.items():
            skill_items.append((name, metadata.description))
        # 排序保证顺序一致
        skill_items.sort()
        return hash(tuple(skill_items))

    def build_base_system_prompt(self) -> str:
        logger.info("Build base system prompt")
        logger.info(f"Workspace dir: {WORKSPACE_DIR}")

        prompt = self._build_prompt_content()
        self.system_prompt = prompt
        self._last_skill_hash = self._get_skill_hash()
        return prompt

    def _build_prompt_content(self) -> str:
        """构建提示词内容（每次调用获取最新skills）"""
        all_skills = self.skill_manager.get_all_skill_descriptions()

        prompt = f"""你是一个智能助手，能够处理各种数据查询和分析任务。

    ## 工作流程

    **重要：你需要按照以下步骤工作：**

    ### 第一步：选择技能或工具
    分析用户的问题，判断应该使用哪个技能来处理。你需要从下面的技能列表中选择最合适的技能。如果找不到合适的技能或工具，就基于内置知识和对用户提供内容的理解进行回答，不可以随便瞎编答案。

    ### 第二步：加载技能
    使用 `skill_load` 工具读取选中技能的 SKILL.md 文件。
    - 格式: `{{"skill_name": "技能名称"}}`

    ### 第三步：执行任务
    技能文件会告诉你：
    - 这个技能的具体作用
    - 如何使用（是否需要调用工具）
    - 返回结果的格式要求

    ### 第四步：返回结果
    严格按照技能文件中定义的输出格式返回结果。

    ## 注意事项
    - 先加载技能工具，再执行任务
    - 技能文件中的工具指令优先级最高
    - 严格按照技能文件要求的格式返回结果

    ## 工作空间目录
    当前工作空间目录为：`{WORKSPACE_DIR}`

    ## 可用工具列表
    - skill_load: Load skill contents
    - file_read: Read file contents
    - file_write: Write to file
    - file_edit: Edit existing file
    - command_execute: Execute command or script
    - web_search: Search information using web search engine
    - web_fetch: Fetch URL content
    - doc_parser: Parses PDF/Word documents to Markdown

    ## 可用技能列表
    以下是所有可用的技能，每个技能都有特定的用途：
    """
        for skill in all_skills:
            prompt += f"- **{skill['name']}**: {skill['description']}\n"

        return prompt

    def get_dynamic_prompt(self) -> str:
        """获取最新的提示词内容（检测skill变化）"""
        return self._build_prompt_content()

    def is_skill_changed(self) -> bool:
        """检测skill是否有变化"""
        return self._get_skill_hash() != self._last_skill_hash

    def update_skill_hash(self):
        """更新skill hash"""
        self._last_skill_hash = self._get_skill_hash()

    def get_system_prompt(self) -> Optional[str]:
        """获取当前系统提示词"""
        return self.system_prompt

    def reset(self):
        """重置提示词"""
        self.system_prompt = None
        self._last_skill_hash = 0
