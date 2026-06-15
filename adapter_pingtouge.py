"""
平头哥实训平台适配器 - PlatformAdapter 的具体实现

展示如何为一个具体平台实现适配器接口。
适配新平台（智慧树、超星、中国大学MOOC等）只需照此模式编写即可。
"""
from __future__ import annotations

import logging

from playwright.async_api import Page

from adapter_base import (
    PlatformAdapter,
    LevelStatus,
    register_adapter,
)
from utils import wait_for_loading_done


@register_adapter("pingtouge")
class PingtougeAdapter(PlatformAdapter):
    """
    平头哥实训平台适配器。

    平台特征:
      - CodeMirror 6 代码编辑器 (.cm-editor, .cm-line)
      - Element UI 单选组件 (label.el-radio)
      - 关卡制，点击「下一关」切换
      - 评测按钮 → 评测记录 tab 查看结果
    """

    platform_name = "平头哥实训平台"

    # ─── 页面检测 ───

    async def detect_page_type(self, page: Page) -> str:
        has_code = await page.query_selector(".cm-editor") is not None
        has_quiz = await page.query_selector("[id^='qusition-']") is not None
        if has_code and has_quiz:
            return "mixed"
        if has_code:
            return "code"
        if has_quiz:
            return "quiz"
        return "code"  # 默认为代码

    # ─── 代码提取 ───

    async def extract_code(self, page: Page, logger: logging.Logger) -> str:
        lines = await page.query_selector_all(".cm-line")
        if not lines:
            logger.warning("未找到 .cm-line 元素")
            return ""
        code_parts = [(await l.text_content() or "") for l in lines]
        code = "\n".join(code_parts)
        logger.debug(f"提取到 {len(lines)} 行代码")
        return code

    # ─── 单选题提取 ───

    async def extract_quiz_answers(
        self, page: Page, logger: logging.Logger
    ) -> dict[str, str | None]:
        answers: dict[str, str | None] = {}
        items = await page.query_selector_all(".li-item")
        for item in items:
            q_div = await item.query_selector("[id^='qusition-']")
            if not q_div:
                continue
            q_id = await q_div.get_attribute("id")
            checked = await item.query_selector(
                "label.el-radio.is-checked input[type='radio']"
            )
            if checked:
                answers[q_id] = await checked.get_attribute("value")
            else:
                answers[q_id] = None
        logger.info(f"提取 {len(answers)} 题单选")
        return answers

    # ─── 关卡导航 ───

    async def get_current_level_name(self, page: Page) -> str:
        try:
            name_el = await page.query_selector(".left-title .name")
            if name_el:
                return (await name_el.text_content()).strip()
            name_el = await page.query_selector(".left-title .title")
            if name_el:
                return (await name_el.text_content()).strip()
        except Exception:
            pass
        return "未知关卡"

    async def has_next_level(self, page: Page) -> bool:
        btn = await page.query_selector("div.submit-btn:has-text('下一关')")
        return btn is not None

    async def click_next_level(self, page: Page, logger: logging.Logger) -> bool:
        btn = await page.query_selector("div.submit-btn:has-text('下一关')")
        if not btn:
            return False
        await btn.click()
        await page.wait_for_timeout(2000)
        logger.info("已点击「下一关」")
        return True

    # ─── 关卡状态表 ───

    async def read_levels_table(self, page: Page) -> list[LevelStatus]:
        levels: list[LevelStatus] = []
        rows = await page.query_selector_all("tr.el-table__row")
        for row in rows:
            cells = await row.query_selector_all("td")
            texts = [(await c.text_content()).strip() for c in cells]
            if len(texts) >= 4:
                levels.append(LevelStatus(
                    name=texts[0] if len(texts) > 0 else "",
                    max_score=texts[1] if len(texts) > 1 else "",
                    my_score=texts[2] if len(texts) > 2 else "",
                    status=texts[5] if len(texts) > 5 else "",
                ))
        return levels

    # ─── 代码填入 ───

    async def fill_code(
        self, page: Page, code: str, logger: logging.Logger
    ) -> bool:
        await wait_for_loading_done(page)
        try:
            await page.keyboard.insert_text(code)
            await page.wait_for_timeout(500)
            lines = await page.query_selector_all(".cm-line")
            actual = "\n".join([(await l.text_content() or "") for l in lines])
            if len(actual.strip()) >= 10:
                return True
        except Exception as e:
            logger.error(f"insert_text 失败: {e}")
        return False

    # ─── 单选题填入 ───

    async def fill_quiz_answer(
        self, page: Page, q_id: str, value: str, logger: logging.Logger
    ) -> bool:
        try:
            q_div = await page.query_selector(f"#{q_id}")
            if not q_div:
                return False
            li = (await q_div.evaluate_handle(
                "el => el.closest('.li-item')"
            )).as_element()
            if not li:
                return False
            label = await li.query_selector(
                f"label.el-radio:has(input[value='{value}'])"
            )
            if not label:
                return False
            if await label.get_attribute("aria-checked") == "true":
                return True  # 已选中
            await label.click()
            await page.wait_for_timeout(200)
            return True
        except Exception as e:
            logger.error(f"{q_id}: {e}")
            return False

    # ─── 评测 ───

    async def click_submit(self, page: Page, logger: logging.Logger) -> bool:
        btn = await page.query_selector("button:has-text('评测')")
        if not btn:
            return False
        await btn.click()
        await page.wait_for_timeout(4000)
        return True

    async def check_result(self, page: Page, logger: logging.Logger) -> bool:
        try:
            tab = await page.query_selector(".item:has-text('评测记录')")
            if not tab:
                return False
            await tab.click()
            await page.wait_for_timeout(1000)
            content = await page.query_selector(".left-content")
            if not content:
                return False
            text = await content.text_content()
            for line in text.strip().split("\n")[:4]:
                if "评测通过" in line:
                    logger.info("✓ 评测通过")
                    return True
                if any(kw in line for kw in ("不成功", "失败", "错误")):
                    logger.warning(f"✗ {line[:80]}")
                    return False
            return False
        except Exception as e:
            logger.warning(f"检查评测结果异常: {e}")
            return False

    # ─── 实验导航 ───

    async def click_start_experiment(
        self, page: Page, exp_name: str, logger: logging.Logger
    ) -> bool:
        await wait_for_loading_done(page)
        await page.wait_for_selector(".li-item", timeout=10_000)
        await page.wait_for_timeout(500)
        items = await page.query_selector_all(".li-item")
        for item in items:
            name_el = await item.query_selector(".title-con")
            name = (await name_el.text_content()).strip() if name_el else ""
            if name == exp_name:
                btn = await item.query_selector("button:has-text('开始实验')")
                if btn:
                    await btn.click()
                    await page.wait_for_timeout(4000)
                    return True
        return False

    async def enter_code_page(self, ctx, logger: logging.Logger):
        """进入代码编辑页面，返回 (code_page, detail_page)"""
        detail = None
        for p in ctx.pages:
            if "/class/combat/detail" in p.url:
                detail = p
                break
        if not detail:
            return None, None

        await detail.bring_to_front()
        await detail.wait_for_load_state("networkidle")
        await wait_for_loading_done(detail)
        await detail.wait_for_timeout(2000)

        enter = await detail.query_selector("button:has-text('进入实验')")
        if enter:
            await enter.click()
            await detail.wait_for_timeout(4000)
            await wait_for_loading_done(detail)

        code_page = None
        for p in ctx.pages:
            if "/class/code" in p.url:
                code_page = p
                break
        if not code_page:
            code_page = detail if "/class/code" in detail.url else None

        if code_page:
            await code_page.bring_to_front()
            await code_page.wait_for_timeout(2000)

        return code_page, detail
