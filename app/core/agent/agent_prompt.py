# core/agent/agent_prompt.py
from typing import List, Dict, Any, Optional
from core.skill.skill_manager import SkillManager
from config.logging_config import get_logger

logger = get_logger(__name__)


class AgentPrompt:
    """
    Agent 提示词管理器
    """

    def __init__(self, skill_manager: Optional[SkillManager] = None):
        """
        初始化提示词管理器

        Args:
            skill_manager: 技能管理器实例，用于获取技能描述
        """
        self.skill_manager = skill_manager
        self.system_prompt: Optional[str] = None

    def set_skill_manager(self, skill_manager: SkillManager):
        self.skill_manager = skill_manager

    def build_base_system_prompt(self) -> str:
        # 获取所有技能描述
        all_skills = []
        if self.skill_manager:
            all_skills = self.skill_manager.get_all_skill_descriptions()

        # 完全保持原有的提示词格式
        prompt = f"""你是一个智能助手，能够处理各种数据查询和分析任务。

    ## 工作流程

    **重要：你需要按照以下步骤工作：**

    ### 第一步：选择技能或工具
    分析用户的问题，判断应该使用哪个技能来处理。你需要从下面的技能列表中选择最合适的技能。如果找不到合适的技能或工具，就基于内置知识和对用户提供内容的理解进行回答，不可以随便瞎编答案。

    ### 第二步：加载技能
    使用 `file_read` 工具读取选中技能的 SKILL.md 文件。
    - 格式: `{{"path": "SKILL.md", "skill_name": "技能名称"}}`

    ### 第三步：执行任务
    技能文件会告诉你：
    - 这个技能的具体作用
    - 如何使用（是否需要调用工具）
    - 返回结果的格式要求

    ### 第四步：返回结果
    严格按照技能文件中定义的输出格式返回结果。

    ## 注意事项
    - 必须先加载技能工具，再执行任务
    - 技能文件中的指令优先级最高
    - 严格按照技能文件要求的格式返回结果

    ## 可用工具列表
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

        self.system_prompt = prompt
        return prompt

    def get_system_prompt(self) -> Optional[str]:
        """获取当前系统提示词"""
        return self.system_prompt

    def reset(self):
        """重置提示词"""
        self.system_prompt = None
