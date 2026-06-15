"""
工具函数 - 日志、重试、等待、截图
"""
from __future__ import annotations

import functools
import logging
import os
import time
from datetime import datetime
from typing import Callable, Awaitable

from playwright.async_api import Page

from config import (
    LOG_DIR,
    LOG_LEVEL,
    LOG_FORMAT,
    MAX_RETRIES,
    RETRY_DELAY,
    SAVE_SCREENSHOTS,
    SCREENSHOT_DIR,
)


def setup_logging(log_name: str = "pingtouge") -> logging.Logger:
    """配置并返回 logger 实例，同时输出到文件和控制台"""
    os.makedirs(LOG_DIR, exist_ok=True)

    logger = logging.getLogger(log_name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 文件 handler（DEBUG 级别，记录更详细）
    log_file = os.path.join(
        LOG_DIR, f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(LOG_FORMAT))

    # 控制台 handler（INFO 级别，简洁输出）
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(LOG_FORMAT))

    logger.addHandler(fh)
    logger.addHandler(ch)

    logger.info(f"日志文件: {log_file}")
    return logger


async def screenshot(
    page: Page, name: str, logger: logging.Logger | None = None
) -> None:
    """保存全页截图到 logs/screenshots/"""
    if not SAVE_SCREENSHOTS:
        return
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(SCREENSHOT_DIR, f"{name}_{timestamp}.png")
    await page.screenshot(path=path, full_page=True)
    if logger:
        logger.info(f"截图已保存: {path}")


def retry_on_fail(
    max_retries: int | None = None,
    delay_ms: int | None = None,
) -> Callable[[Callable[..., Awaitable]], Callable[..., Awaitable]]:
    """装饰器：操作失败时自动重试"""
    def decorator(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            _max = max_retries if max_retries is not None else MAX_RETRIES
            _delay = delay_ms if delay_ms is not None else RETRY_DELAY
            last_error: Exception | None = None

            for attempt in range(1, _max + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    # 尝试从 args 中找到 logger
                    for arg in args:
                        if isinstance(arg, logging.Logger):
                            arg.warning(
                                f"{func.__name__} 第 {attempt}/{_max} 次尝试失败: {e}"
                            )
                            break
                    if attempt < _max:
                        time.sleep(_delay / 1000)

            raise last_error  # type: ignore[misc]

        return wrapper
    return decorator


def log_step(logger: logging.Logger, step: str, account: str = "") -> None:
    """打印步骤日志，可选带账号前缀"""
    prefix = f"[{account}] " if account else ""
    logger.info(f"{prefix}{step}")


async def wait_for_loading_done(page, logger=None, timeout=15_000) -> bool:
    """
    等待页面遮罩层（Element UI loading mask）消失。

    许多在线教育平台使用 el-loading-mask 覆盖页面，
    在此期间点击任何元素都会失败。此函数轮询等待其消失。
    """
    import asyncio as _asyncio
    deadline = time.monotonic() + timeout / 1000
    while time.monotonic() < deadline:
        mask = await page.query_selector(".el-loading-mask")
        if not mask:
            return True
        # 检查是否可见（有些 mask 是隐藏的）
        visible = await mask.evaluate("el => el.offsetParent !== null")
        if not visible:
            return True
        await _asyncio.sleep(0.5)
    if logger:
        logger.warning(f"等待 loading mask 消失超时 ({timeout}ms)，继续执行")
    return False
