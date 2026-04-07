from typing import Dict, Any, List, Optional, Set, Tuple
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from core.skill_loader import SkillLoader, SkillMetadata
from core.tools.file_read_tool import FileReadTool
from core.tools.es_search_data_tool import SearchDataTool
from core.tools.mcp_client import MCPClientManager
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)


class ProgressiveAgent:
    """
    渐进式Agent - 动态工具加载
    让AI自己选择需要加载的技能
    """

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = skills_dir
        self.skill_loader = SkillLoader(skills_dir)
        self.skill_loader.load_all_skills()

        # 基础工具（始终可用）
        self.file_read_tool = FileReadTool(skills_dir)
        self.search_tool = SearchDataTool()
        self.base_tools = [self.file_read_tool, self.search_tool]

        # MCP相关
        self.mcp_manager: Optional[MCPClientManager] = None
        self.mcp_tools: List = []
        self.use_mcp = settings.USE_MCP

        # LLM相关
        self.llm: Optional[ChatOpenAI] = None
        self.agent_executor: Optional[AgentExecutor] = None
        self.system_prompt: Optional[str] = None

    async def initialize(self):
        """初始化Agent"""
        try:
            self._init_llm()

            # 如果需要，加载MCP工具
            if self.use_mcp:
                await self._load_mcp_tools()

            # 构建基础系统提示词
            self._build_base_system_prompt()

            # 创建基础Agent（只有file_read和MCP工具）
            all_tools = self.base_tools + self.mcp_tools
            self._create_agent_executor(all_tools)

            logger.info(f"ProgressiveAgent初始化完成，模式: {self.get_mode()}, 基础工具数: {len(all_tools)}")
            return self

        except Exception as e:
            logger.error(f"ProgressiveAgent初始化失败: {str(e)}")
            raise

    def _init_llm(self):
        """初始化LLM"""
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY 未设置")

        self.llm = ChatOpenAI(
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
        )
        logger.info(f"LLM初始化成功: {settings.LLM_MODEL}")

    async def _load_mcp_tools(self):
        """加载MCP工具"""
        try:
            logger.info(f"正在连接到MCP服务器: {settings.MCP_SERVER_URL}")
            self.mcp_manager = MCPClientManager(settings.MCP_SERVER_URL)
            self.mcp_tools = await self.mcp_manager.initialize()
            logger.info(f"从MCP加载了 {len(self.mcp_tools)} 个工具")
        except Exception as e:
            logger.error(f"MCP连接失败: {str(e)}")
            self.use_mcp = False
            logger.warning("MCP连接失败，将仅使用本地工具")

    def _create_agent_executor(self, tools: List):
        """创建Agent执行器"""
        prompt = self._create_prompt_template()

        agent = create_openai_tools_agent(
            llm=self.llm,
            tools=tools,
            prompt=prompt
        )

        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=settings.MAX_ITERATIONS,
            early_stopping_method="generate",
            return_intermediate_steps=True
        )

        logger.debug(f"Agent执行器创建完成，工具数: {len(tools)}")

    def _create_prompt_template(self) -> ChatPromptTemplate:
        """创建提示词模板"""
        return ChatPromptTemplate.from_messages([
            ("system", "{system_prompt}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

    def _build_base_system_prompt(self):
        """构建基础系统提示词（未加载技能时）"""
        all_skills = self.skill_loader.get_all_skill_descriptions()

        prompt = f"""你是一个智能助手，能够处理各种数据查询和分析任务。

## 可用技能列表

以下是所有可用的技能，每个技能都有特定的用途：

"""
        for skill in all_skills:
            prompt += f"- **{skill['name']}**: {skill['description']}\n"

        prompt += """
## 工作流程

**重要：你需要按照以下步骤工作：**

### 第一步：选择技能
分析用户的问题，判断应该使用哪个技能来处理。你需要从上面的技能列表中选择最合适的技能。如果找不到合适的技能或工具，就基于内置知识和对用户提供内容的理解进行回答，不可以随便瞎编答案。

### 第二步：加载技能
使用 `file_read` 工具读取选中技能的 SKILL.md 文件。
- 格式: `{"path": "SKILL.md", "skill_name": "技能名称"}`

### 第三步：执行任务
技能文件会告诉你：
- 这个技能的具体作用
- 如何使用（是否需要调用工具）
- 返回结果的格式要求

### 第四步：返回结果
严格按照技能文件中定义的输出格式返回结果。

## 可用工具

- **file_read**: 读取技能文件，获取详细的执行指令

## 示例

### 示例1：数据查询类任务
用户: "查询今天的高危告警"

你应该：
1. 选择技能: data-search
2. 调用: file_read(path="data-search/SKILL.md")
3. 按技能指示使用 search_data 工具查询数据

### 示例2：分析解读类任务
用户: "请分析这条告警: {{...}}"

你应该：
1. 选择技能: log-alert-explain
2. 调用: file_read(path="log-alert-explain/SKILL.md")
3. 按技能指示进行分析，不需要调用工具

## 注意事项

- **必须**先加载技能文件，再执行任务
- 技能文件中的指令优先级最高
- 严格按照技能文件要求的格式返回结果
"""
        self.system_prompt = prompt

    async def process(self, message: str, chat_history: Optional[List] = None) -> Dict[str, Any]:
        """
        处理用户消息
        让AI自己决定使用哪个技能
        """
        if not self.agent_executor:
            raise RuntimeError("Agent未初始化")

        # 直接处理消息，让AI自己决定如何执行
        # AI会根据系统提示词中的"可用技能列表"和"工作流程"来决定：
        # 1. 是否需要加载技能
        # 2. 加载哪个技能
        # 3. 是否需要调用工具

        input_data = {
            "system_prompt": self.system_prompt,
            "input": message,
            "chat_history": chat_history or []
        }

        return await self.agent_executor.ainvoke(input_data)

    async def close(self):
        """关闭连接"""
        if self.mcp_manager:
            await self.mcp_manager.close()
            logger.info("MCP连接已关闭")

    def get_tools_info(self) -> List[dict]:
        """获取所有工具信息"""
        tools_info = []

        # 基础工具
        for tool in self.base_tools:
            tools_info.append({
                "name": getattr(tool, 'name', str(tool)),
                "description": getattr(tool, 'description', 'No description'),
                "type": "base_tool",
                "is_high_risk": hasattr(tool, 'name') and tool.name in settings.HIGH_RISK_TOOLS
            })

        # MCP工具
        for tool in self.mcp_tools:
            tools_info.append({
                "name": getattr(tool, 'name', str(tool)),
                "description": getattr(tool, 'description', 'No description'),
                "type": "mcp_tool",
                "is_high_risk": hasattr(tool, 'name') and tool.name in settings.HIGH_RISK_TOOLS
            })

        # 技能列表
        # skills = self.skill_loader.get_all_skill_descriptions()
        # for skill in skills:
        #     tools_info.append({
        #         "name": skill["name"],
        #         "description": skill["description"],
        #         "type": "skill",
        #         "is_high_risk": False
        #     })

        return tools_info

    def get_mode(self) -> str:
        """获取当前模式"""
        if self.use_mcp and self.mcp_tools:
            return "progressive_with_mcp"
        elif self.use_mcp:
            return "progressive_mcp_failed"
        else:
            return "progressive_local"
