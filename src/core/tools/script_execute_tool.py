from typing import Optional, Type, Dict, Any, List
from langchain.tools import BaseTool
from pydantic import BaseModel, Field, ConfigDict
from pathlib import Path
from config.logging_config import get_logger
from utils.command_executor import execute_local_command, DEFAULT_COMMAND_TIMEOUT

logger = get_logger(__name__)


class ScriptExecuteInput(BaseModel):
    """脚本执行工具的输入参数"""
    script: str = Field(description="要执行的完整命令（包含解释器，如：python script.py、bash script.sh、node script.js）")
    working_dir: Optional[str] = Field(
        default=None,
        description="脚本执行的工作目录"
    )
    timeout: int = Field(
        default=30,
        description="脚本执行超时时间（秒），默认30秒"
    )
    args: Optional[str] = Field(
        default=None,
        description="传递给脚本的命令行参数"
    )


class ScriptExecuteTool(BaseTool):
    """
    脚本执行工具
    Agent通过此工具执行各种类型的脚本（Python、Shell、Node.js等）
    script参数直接包含完整的命令和解释器信息

    支持多种脚本类型：
    1. Python脚本：python script.py 或 python3 script.py
    2. Shell脚本：bash script.sh 或 sh script.sh
    3. Node.js/JavaScript脚本：node script.js
    """

    name: str = "script_execute"
    description: str = """
    执行脚本代码或脚本文件。script参数需要包含完整的命令和解释器信息。

    使用示例：
    1. 执行Python文件：{"script": "python /path/to/script.py"}
    2. 执行Shell命令：{"script": "bash -c 'ls -la'"}
    3. 执行Node.js代码：{"script": "node -e 'console.log(\"Hello\");'"}
    4. 带参数执行：{"script": "python /path/to/script.py", "args": "--verbose --debug"}
    5. 执行Python代码：{"script": "python3 -c 'print(\"Hello World\")'"}

    注意：
    - 脚本执行有超时限制（默认30秒）
    - 输出会被截断以防止过大的输出（默认100000字符）
    - 工作目录可以指定，默认使用当前目录
    """
    args_schema: Type[BaseModel] = ScriptExecuteInput

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def _execute_script(
            self,
            script: str,
            working_dir: Optional[str] = None,
            timeout: int = 30,
            args: Optional[str] = None
    ) -> str:
        """
        执行脚本

        Args:
            script: 完整的命令（包含解释器）
            working_dir: 工作目录
            timeout: 超时时间
            args: 命令行参数

        Returns:
            执行结果
        """
        try:
            # 构建完整命令
            command = script
            if args:
                command = f"{script} {args}"

            # 执行命令
            logger.info(f"execute script: {command}, cwd: {working_dir}, timeout: {timeout}")
            result = execute_local_command(
                command=command,
                cwd=working_dir,
                timeout=timeout
            )

            # 格式化输出
            output = result.output
            if result.exit_code != 0:
                logger.info(f"execute script failed: {command}\n{output}")
                output = f"Script execute failed (exit_code: {result.exit_code})\n{output}"

            if result.truncated:
                output += "\n\nWarning: script execute result is truncated (exceeds the size limit)"

            return output

        except Exception as e:
            logger.error(f"execute script error: {e}", exc_info=True)
            return f"Error: execute script failed - {str(e)}"

    def _run(
            self,
            script: str,
            working_dir: Optional[str] = None,
            timeout: int = 30,
            args: Optional[str] = None
    ) -> str:
        """
        同步执行脚本

        Args:
            script: 完整的命令（包含解释器）
            working_dir: 工作目录
            timeout: 超时时间
            args: 命令行参数

        Returns:
            执行结果
        """
        try:
            # 记录执行信息
            logger.info(f"execute script: {script}, args: {args}")
            if working_dir:
                logger.info(f"working directory: {working_dir}")
            else:
                working_dir = "skills"
                logger.info(f"working directory: {working_dir}")
            if timeout != DEFAULT_COMMAND_TIMEOUT:
                logger.info(f"timeout: {timeout} seconds")

            # 执行脚本
            result = self._execute_script(
                script=script,
                working_dir=working_dir,
                timeout=timeout,
                args=args
            )

            return result

        except Exception as e:
            logger.error(f"script execute failed: {e}", exc_info=True)
            return f"script execute failed: {str(e)}"

    async def _arun(
            self,
            script: str,
            working_dir: Optional[str] = None,
            timeout: int = 30,
            args: Optional[str] = None
    ) -> str:
        """异步执行脚本"""
        # 目前使用同步实现，因为execute_local_command是同步的
        return self._run(script, working_dir, timeout, args)
