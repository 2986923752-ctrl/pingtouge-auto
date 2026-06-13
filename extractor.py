"""
答案提取器 - 从已做完的作业页面提取答案

支持两种场景:
  1. 试卷/单选题: Element UI <el-radio-group>，选中项标记 is-checked
  2. 编程实训题(combat/code): CodeMirror 6 代码编辑器 + 关卡制
"""
from __future__ import annotations

import logging
from typing import Any

from playwright.async_api import Page

from utils import log_step


async def extract_quiz_answers(
    page: Page,
    logger: logging.Logger,
) -> dict[str, str | None]:
    """
    提取单选题答案（适用于 /class/paper 试卷页面）。

    返回:
        { "qusition-0-0": "value_of_selected_option", ... }
    """
    log_step(logger, "正在提取单选题答案...")

    quiz_items = await page.query_selector_all(".li-item")
    answers: dict[str, str | None] = {}

    for idx, item in enumerate(quiz_items):
        try:
            q_div = await item.query_selector("[id^='qusition-']")
            if not q_div:
                continue
            q_id = await q_div.get_attribute("id")

            checked_radio = await item.query_selector(
                "label.el-radio.is-checked input[type='radio']"
            )
            if checked_radio:
                value = await checked_radio.get_attribute("value")
                answers[q_id] = value
                logger.debug(
                    f"  {q_id} → {value[:50] if value and len(value) > 50 else value}"
                )
            else:
                logger.warning(f"  {q_id}: 未找到选中项")
                answers[q_id] = None

        except Exception as e:
            logger.warning(f"  第 {idx + 1} 题提取失败: {e}")

    logger.info(
        f"单选题提取完成: {len(answers)} 题, "
        f"有答案 {sum(1 for v in answers.values() if v)} 题"
    )
    return answers


async def extract_code_from_editor(
    page: Page,
    logger: logging.Logger,
) -> str:
    """
    从当前页面的 CodeMirror 编辑器提取代码。

    返回:
        str: 完整代码文本
    """
    lines = await page.query_selector_all(".cm-line")
    if not lines:
        logger.warning("未找到 .cm-line 元素")
        return ""

    code_parts: list[str] = []
    for line in lines:
        text = await line.text_content() or ""
        code_parts.append(text)

    code = "\n".join(code_parts)
    logger.debug(f"提取到 {len(lines)} 行代码")
    return code


async def get_current_level_name(page: Page) -> str:
    """获取当前关卡名称"""
    try:
        # 关卡名在标题区域（左侧面板的标题，不是用户信息里的name）
        name_el = await page.query_selector(".left-title .name")
        if name_el:
            return (await name_el.text_content()).strip()
        # 备选: .title（不含用户信息）
        name_el = await page.query_selector(".left-title .title")
        if name_el:
            return (await name_el.text_content()).strip()
        # 再备选: 第二个 .name（第一个是用户名）
        names = await page.query_selector_all(".name")
        if len(names) >= 2:
            return (await names[1].text_content()).strip()
    except Exception:
        pass
    return "未知关卡"


async def has_next_level(page: Page) -> bool:
    """检查是否有下一关按钮"""
    btn = await page.query_selector("div.submit-btn:has-text('下一关')")
    return btn is not None


async def click_next_level(page: Page, logger: logging.Logger) -> bool:
    """
    点击「下一关」按钮。

    返回:
        bool: 是否成功切换到下一关
    """
    btn = await page.query_selector("div.submit-btn:has-text('下一关')")
    if not btn:
        logger.info("未找到「下一关」按钮，可能是最后一关")
        return False

    await btn.click()
    await page.wait_for_timeout(2000)
    logger.info("已点击「下一关」")
    return True


async def read_combat_levels(page: Page) -> list[dict[str, str]]:
    """
    从 combat/detail 页面的表格读取所有关卡状态。

    返回:
        [
            {"name": "函数的定义", "max_score": "10", "my_score": "10",
             "attempts": "2", "time": "2026-05-15 11:54:19", "status": "已提交"},
            ...
        ]
    """
    levels: list[dict[str, str]] = []
    rows = await page.query_selector_all("tr.el-table__row")
    for row in rows:
        cells = await row.query_selector_all("td")
        texts = [(await c.text_content()).strip() for c in cells]
        if len(texts) >= 4:
            levels.append({
                "name": texts[0] if len(texts) > 0 else "",
                "max_score": texts[1] if len(texts) > 1 else "",
                "my_score": texts[2] if len(texts) > 2 else "",
                "attempts": texts[3] if len(texts) > 3 else "",
                "time": texts[4] if len(texts) > 4 else "",
                "status": texts[5] if len(texts) > 5 else "",
            })
    return levels


async def extract_code_levels(
    page: Page,
    logger: logging.Logger,
    max_levels: int | None = None,
) -> list[dict[str, Any]]:
    """
    遍历代码关卡，提取每关的答案。

    参数:
        max_levels: 最多提取几关（None=全部，1=只提取当前关）

    返回:
        [{"name": "...", "code": "..."}, ...]
    """
    log_step(logger, f"开始遍历代码关卡 (上限: {max_levels or '全部'})...")
    all_levels: list[dict[str, Any]] = []
    level_idx = 0
    safety_limit = max_levels if max_levels else 20

    while level_idx < safety_limit:
        level_idx += 1

        await page.wait_for_timeout(1000)

        editor = await page.query_selector(".cm-editor")
        if not editor:
            logger.warning(f"第 {level_idx} 关未找到编辑器")
            break

        level_name = await get_current_level_name(page)
        log_step(logger, f"提取第 {level_idx} 关: {level_name}")

        code = await extract_code_from_editor(page, logger)
        all_levels.append({"name": level_name, "index": level_idx, "code": code})
        logger.info(f"  ✓ [{level_name}]: {len(code)} 字符")

        if not await has_next_level(page):
            logger.info(f"已到最后一关，共 {level_idx} 关")
            break

        await click_next_level(page, logger)

    logger.info(f"代码关卡提取完成: 共 {len(all_levels)} 关")
    return all_levels


async def extract_all_answers(
    page: Page,
    logger: logging.Logger,
    page_type: str = "auto",
    max_code_levels: int | None = None,
) -> dict[str, Any]:
    """
    自动检测页面类型并提取答案。

    参数:
        page_type: "auto" | "quiz" | "code"
        max_code_levels: 最多提取几关代码（None=全部）

    返回:
        {
            "type": "quiz" | "code",
            "quiz": { ... },
            "code_levels": [{"name":..., "code":...}],
        }
    """
    log_step(logger, "========== 开始提取答案 ==========")

    resolved_type = page_type
    if page_type == "auto":
        has_code_editor = await page.query_selector(".cm-editor") is not None
        has_quiz = await page.query_selector("[id^='qusition-']") is not None
        resolved_type = "code" if has_code_editor else "quiz" if has_quiz else "code"

    logger.info(f"页面类型: {resolved_type}, 关卡上限: {max_code_levels or '全部'}")

    result: dict[str, Any] = {"type": resolved_type}
    if resolved_type == "quiz":
        result["quiz"] = await extract_quiz_answers(page, logger)
        result["code_levels"] = []
    elif resolved_type == "code":
        result["quiz"] = {}
        result["code_levels"] = await extract_code_levels(
            page, logger, max_levels=max_code_levels
        )

    logger.info(
        f"提取总结: 类型={resolved_type}, "
        f"单选{len(result.get('quiz', {}))}题, "
        f"代码{len(result.get('code_levels', []))}关"
    )
    return result
