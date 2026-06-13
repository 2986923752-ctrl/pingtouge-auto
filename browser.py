"""
浏览器管理 - 启动、登录、切换账号、导航
"""
from __future__ import annotations

import logging

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config import (
    LOGIN_URL,
    DEFAULT_TIMEOUT,
    PAGE_LOAD_TIMEOUT,
    HEADLESS,
    SLOW_MO,
    VIEWPORT_WIDTH,
    VIEWPORT_HEIGHT,
)
from utils import screenshot, log_step


async def launch_browser() -> tuple[async_playwright, Browser]:
    """启动 Playwright 和 Chromium 浏览器"""
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(
        headless=HEADLESS,
        slow_mo=SLOW_MO,
    )
    return pw, browser


async def create_context(browser: Browser) -> BrowserContext:
    """创建新的浏览器上下文（隔离的 cookie/localStorage 会话）"""
    context = await browser.new_context(
        viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
        locale="zh-CN",
    )
    return context


async def login(
    page: Page,
    username: str,
    password: str,
    logger: logging.Logger,
) -> bool:
    """
    登录平头哥平台。

    参数:
        page: Playwright Page 对象
        username: 账号
        password: 密码
        logger: 日志记录器

    返回:
        bool: 登录是否成功
    """
    log_step(logger, "正在打开登录页面...", username)

    try:
        await page.goto(
            LOGIN_URL, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT
        )
        await page.wait_for_timeout(1000)
    except Exception as e:
        logger.error(f"无法访问登录页面: {e}")
        return False

    # 等待登录表单加载
    try:
        await page.wait_for_selector(
            'input[placeholder="请输入账号"]',
            timeout=DEFAULT_TIMEOUT,
        )
        await page.wait_for_selector(
            'input[placeholder="请输入密码"]',
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception as e:
        logger.error(f"登录表单加载超时: {e}")
        await screenshot(page, f"login_form_timeout_{username}", logger)
        return False

    # 填入账号密码
    log_step(logger, "正在输入账号密码...", username)
    await page.fill('input[placeholder="请输入账号"]', username)
    await page.fill('input[placeholder="请输入密码"]', password)

    # 点击登录
    log_step(logger, "正在点击登录...", username)
    await page.click("button.login-btn")

    # 等待登录响应和页面跳转
    await page.wait_for_timeout(3000)

    # 检查是否登录成功
    # 登录成功后页面会跳转（不再是 /login），且右上角会显示用户名
    current_url = page.url
    if "/login" not in current_url:
        log_step(logger, "登录成功!", username)
        return True

    # 检查错误提示
    error_el = await page.query_selector(".el-message--error")
    if error_el:
        error_text = await error_el.text_content()
        logger.error(f"登录失败，错误信息: {error_text}")
    else:
        logger.error("登录失败，仍在登录页面")

    await screenshot(page, f"login_failed_{username}", logger)
    return False


async def navigate_to_assignment(
    page: Page,
    assignment_url: str,
    logger: logging.Logger,
) -> bool:
    """
    跳转到指定作业页面。

    参数:
        page: Playwright Page 对象
        assignment_url: 作业页面的完整 URL
        logger: 日志记录器

    返回:
        bool: 是否成功跳转
    """
    log_step(logger, f"正在打开作业页面: {assignment_url}")

    try:
        await page.goto(
            assignment_url, wait_until="networkidle", timeout=PAGE_LOAD_TIMEOUT
        )
        await page.wait_for_timeout(1500)
        logger.info("作业页面加载完成")
        return True
    except Exception as e:
        logger.error(f"作业页面加载失败: {e}")
        await screenshot(page, "assignment_load_failed", logger)
        return False


async def logout(page: Page, logger: logging.Logger) -> None:
    """退出登录"""
    log_step(logger, "正在退出登录...")
    try:
        user_box = await page.query_selector(".user-box")
        if user_box:
            await user_box.click()
            await page.wait_for_timeout(500)
            logout_btn = await page.query_selector("text=退出登录")
            if logout_btn:
                await logout_btn.click()
                await page.wait_for_timeout(1000)
                logger.info("已退出登录")
    except Exception as e:
        logger.warning(f"退出登录时出错: {e}")


async def close_context(context: BrowserContext) -> None:
    """关闭浏览器上下文"""
    await context.close()
