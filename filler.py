"""
答案填充器 - 填入答案并自检验证（只使用 insert_text，已验证 100% 可靠）
"""
from __future__ import annotations

import logging

from playwright.async_api import Page

from utils import log_step


# ─── 编辑器操作 ───

async def _clear_editor(page: Page, logger: logging.Logger) -> bool:
    """清空 CodeMirror 编辑器"""
    await page.wait_for_selector(".cm-editor", timeout=10_000)
    await page.wait_for_timeout(500)

    is_mac: bool = await page.evaluate("() => navigator.platform.includes('Mac')")
    mod = "Meta" if is_mac else "Control"

    editor = await page.query_selector(".cm-editor")
    if not editor:
        return False
    await editor.click()
    await page.wait_for_timeout(300)
    await page.keyboard.press(f"{mod}+A")
    await page.wait_for_timeout(100)
    await page.keyboard.press("Backspace")
    await page.wait_for_timeout(300)
    return True


async def _fill_editor(page: Page, code: str, logger: logging.Logger) -> bool:
    """只用 insert_text（100% 保持缩进，触发 CM6 更新）"""
    try:
        await page.keyboard.insert_text(code)
        await page.wait_for_timeout(500)
        lines = await page.query_selector_all(".cm-line")
        actual = "\n".join([(await l.text_content() or "") for l in lines])
        if len(actual.strip()) >= 10:
            return True
    except Exception as e:
        logger.error(f"  insert_text 失败: {e}")
    return False


async def fill_code_to_editor(page: Page, code: str, logger: logging.Logger) -> bool:
    """安全填入代码: 等待编辑器 → 清空 → insert_text → 验证"""
    await page.wait_for_selector(".cm-editor", timeout=15_000)
    await page.wait_for_timeout(800)

    await _clear_editor(page, logger)
    ok = await _fill_editor(page, code, logger)
    if not ok:
        logger.error("  代码填入失败")
        return False

    lines = await page.query_selector_all(".cm-line")
    actual = "\n".join([(await l.text_content() or "") for l in lines])
    if len(actual.strip()) >= len(code.strip()) * 0.5:
        return True
    else:
        logger.warning(f"  填入验证失败: 期望{len(code)}字符, 实际{len(actual)}字符")
        return False


# ─── 评测与验证 ───

async def click_evaluate(page: Page, logger: logging.Logger) -> bool:
    """点击「评测」按钮"""
    btn = await page.query_selector("button:has-text('评测')")
    if not btn:
        return False
    await btn.click()
    await page.wait_for_timeout(4000)
    return True


async def check_evaluation_result(page: Page, logger: logging.Logger) -> bool:
    """点击评测记录 tab，检查最新记录是否通过"""
    try:
        record_tab = await page.query_selector(".item:has-text('评测记录')")
        if not record_tab:
            return False
        await record_tab.click()
        await page.wait_for_timeout(1000)

        content = await page.query_selector(".left-content")
        if not content:
            return False
        text = await content.text_content()

        lines = text.strip().split("\n")
        for line in lines[:4]:  # 最新记录在前4行
            if "评测通过" in line:
                logger.info("  ✓ 评测通过")
                return True
            if "不成功" in line or "失败" in line or "错误" in line:
                logger.warning(f"  ✗ {line[:80]}")
                return False
        return False
    except Exception as e:
        logger.warning(f"  检查评测结果异常: {e}")
        return False


async def has_next_level(page: Page) -> bool:
    """检查是否有下一关按钮"""
    return await page.query_selector("div.submit-btn:has-text('下一关')") is not None


async def click_next_level(page: Page, logger: logging.Logger) -> bool:
    """点击「下一关」按钮，等待新编辑器加载"""
    btn = await page.query_selector("div.submit-btn:has-text('下一关')")
    if not btn:
        return False
    await btn.click()
    await page.wait_for_timeout(1500)
    await page.wait_for_selector(".cm-editor", timeout=10_000)
    await page.wait_for_timeout(1000)
    logger.info("  已点击「下一关」")
    return True


# ─── 主流程 ───

async def fill_and_evaluate_one_level(
    page: Page,
    code: str,
    level_name: str,
    logger: logging.Logger,
    max_retries: int = 2,
) -> bool:
    """填入代码并评测，支持重试"""
    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            logger.info(f"  [{level_name}] 第 {attempt} 次重试...")

        fill_ok = await fill_code_to_editor(page, code, logger)
        if not fill_ok:
            continue

        await click_evaluate(page, logger)
        passed = await check_evaluation_result(page, logger)
        if passed:
            return True
        await page.wait_for_timeout(1000)

    logger.error(f"  [{level_name}] 评测 {max_retries} 次均失败")
    return False


async def fill_code_levels(
    page: Page,
    code_levels: list[dict],
    logger: logging.Logger,
    submit_each: bool = True,
) -> bool:
    """遍历填入所有代码关卡"""
    if not code_levels:
        logger.info("无代码关卡需要填入")
        return True

    logger.info(f"开始填入代码关卡，共 {len(code_levels)} 关...")
    all_passed = True

    for idx, level_info in enumerate(code_levels):
        level_name = level_info.get("name", f"第{idx + 1}关")
        code: str = level_info.get("code", "")
        if not code:
            logger.warning(f"  关卡 [{level_name}]: 代码为空")
            all_passed = False
            continue

        await page.wait_for_timeout(1000)
        editor = await page.query_selector(".cm-editor")
        if not editor:
            logger.error(f"  关卡 [{level_name}]: 未找到编辑器")
            all_passed = False
            continue

        logger.info(f"  关卡 [{level_name}] ({len(code)} 字符)")
        if submit_each:
            if not await fill_and_evaluate_one_level(
                page, code, level_name, logger
            ):
                all_passed = False
        else:
            await fill_code_to_editor(page, code, logger)

        if idx < len(code_levels) - 1:
            if await has_next_level(page):
                await click_next_level(page, logger)
            else:
                break

    return all_passed


async def fill_quiz_answers(
    page: Page, answers: dict[str, str | None], logger: logging.Logger
) -> bool:
    """填入单选题答案"""
    all_done = True
    for q_id, target_value in answers.items():
        if target_value is None:
            continue
        try:
            q_div = await page.query_selector(f"#{q_id}")
            if not q_div:
                continue
            li_item_el = (
                await q_div.evaluate_handle("el => el.closest('.li-item')")
            ).as_element()
            if not li_item_el:
                continue
            target_label = await li_item_el.query_selector(
                f"label.el-radio:has(input[value='{target_value}'])"
            )
            if not target_label:
                continue
            if await target_label.get_attribute("aria-checked") == "true":
                continue
            await target_label.click()
            await page.wait_for_timeout(200)
        except Exception as e:
            logger.error(f"  {q_id}: {e}")
            all_done = False
    return all_done


async def fill_all_answers(
    page: Page, answers: dict, logger: logging.Logger
) -> bool:
    """
    根据答案类型自动填入。

    answers 格式:
        {"type": "quiz", "quiz": { ... }}
        {"type": "code", "code_levels": [...]}
    """
    log_step(logger, "========== 开始填入答案 ==========")
    page_type: str = answers.get("type", "code")
    if page_type == "quiz":
        return await fill_quiz_answers(page, answers.get("quiz", {}), logger)
    elif page_type == "code":
        return await fill_code_levels(
            page, answers.get("code_levels", []), logger
        )
    return False
