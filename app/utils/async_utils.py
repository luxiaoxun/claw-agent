import asyncio
import threading
from typing import TypeVar, Coroutine, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from config.logging_config import get_logger

logger = get_logger(__name__)
T = TypeVar('T')

# 全局事件循环和线程
_loop = None
_loop_thread = None
_loop_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="async_worker")


def _get_or_create_event_loop():
    """获取或创建持久化事件循环"""
    global _loop, _loop_thread

    with _loop_lock:
        if _loop is None or _loop.is_closed():
            _loop = asyncio.new_event_loop()
            _loop_thread = threading.Thread(target=_run_loop, args=(_loop,), daemon=True)
            _loop_thread.start()
            logger.info("创建了持久化事件循环和线程")
        return _loop


def _run_loop(loop):
    """在独立线程中运行事件循环"""
    asyncio.set_event_loop(loop)
    try:
        loop.run_forever()
    except Exception as e:
        logger.error(f"事件循环运行错误: {e}")
    finally:
        try:
            # 清理未完成的任务
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
        except:
            pass


def run_async(coro: Coroutine[Any, Any, T], timeout: Optional[int] = None) -> T:
    """
    在同步上下文中运行异步代码

    支持两种模式：
    1. 使用持久化事件循环（默认）
    2. 如果当前线程已有运行中的事件循环，使用线程池

    Args:
        coro: 要执行的协程
        timeout: 超时时间（秒），None表示不超时

    Returns:
        协程执行结果
    """
    try:
        # 尝试获取当前线程的事件循环
        current_loop = asyncio.get_event_loop()
        if current_loop.is_running():
            # 当前线程有运行中的事件循环
            # 不能直接使用，需要在线程池中执行
            logger.debug("当前线程有运行中的事件循环，使用线程池")
            future = _executor.submit(asyncio.run, coro)
            if timeout:
                return future.result(timeout=timeout)
            else:
                return future.result()
    except RuntimeError:
        # 当前线程没有事件循环，正常处理
        pass

    # 使用持久化事件循环
    loop = _get_or_create_event_loop()
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    if timeout:
        return future.result(timeout=timeout)
    else:
        return future.result()


def run_async_with_timeout(coro: Coroutine[Any, Any, T], timeout: int = 30) -> T:
    """
    在同步上下文中运行异步代码，带超时控制
    """
    return run_async(coro, timeout)


def cleanup_loop():
    """清理事件循环（应用关闭时调用）"""
    global _loop
    with _loop_lock:
        if _loop and not _loop.is_closed():
            _loop.call_soon_threadsafe(_loop.stop)
            _loop = None
    _executor.shutdown(wait=False)
    logger.info("清理事件循环完成")
