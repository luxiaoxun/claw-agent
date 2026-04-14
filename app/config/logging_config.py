import os
import logging
from loguru import logger
import sys
from config.settings import WORK_DIR


class InterceptHandler(logging.Handler):
    """拦截标准logging并重定向到loguru"""

    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging():
    """配置日志系统"""
    # 创建logs目录
    log_dir = os.path.join(WORK_DIR, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    # 移除默认处理器
    logger.remove()

    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True
    )

    # 添加文件处理器 - 每天0点回滚，保留30天
    logger.add(
        os.path.join(log_dir, "app.{time:YYYY-MM-DD}.log"),
        rotation="00:00",  # 每天0点回滚
        retention=30,  # 保留30天
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level="INFO",
        encoding="utf-8"
    )

    # 拦截标准logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 设置第三方库的日志级别
    for logger_name in ["urllib3", "httpx", "httpcore"]:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


def get_logger(name: str):
    """获取logger实例"""
    return logger.bind(name=name)
