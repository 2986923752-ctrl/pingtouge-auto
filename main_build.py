"""
答案库构建器 - 从已完成作业的源账号提取答案，生成 answer_bank.json

用法:
  python main_build.py                              # 从配置的课堂 URL 提取
  python main_build.py --classroom <URL>            # 指定课堂 URL
  python main_build.py --account <user> --password <pwd>  # 指定源账号
  python main_build.py --output my_bank.json        # 指定输出文件
"""
import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    ANSWER_BANK_PATH,
    CLASSROOM_URL,
    DEFAULT_PASSWORD,
    HEADLESS,
)
from browser import launch_browser, create_context, login, close_context
from extractor import extract_all_answers, read_combat_levels
from utils import setup_logging, screenshot


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="平头哥实训平台 - 答案库构建器"
    )
    p.add_argument("--account", type=str, default=None,
                   help="源账号（不指定则读取 answer_bank.json 中已有的 source_account）")
    p.add_argument("--password", type=str, default=DEFAULT_PASSWORD,
                   help="源账号密码")
    p.add_argument("--classroom", type=str, default=CLASSROOM_URL,
                   help="课堂 URL")
    p.add_argument("--output", type=str, default=ANSWER_BANK_PATH,
                   help="输出 JSON 文件路径")
    p.add_argument("--headless", action="store_true", help="无头模式")
    p.add_argument("--append", action="store_true",
                   help="追加模式：合并到已有答案库，不覆盖已有实验")
    return p.parse_args()


async def get_weeks(page) -> list[str]:
    """扫描课堂页面所有周标签"""
    return await page.evaluate("""
        () => Array.from(document.querySelectorAll('span'))
            .filter(s => s.textContent.trim().startsWith('Python第') && s.textContent.trim().endsWith('周'))
            .map(s => s.textContent.trim())
    """)


async def scan_experiments(page) -> list[dict]:
    """扫描当前周的实验列表"""
    await page.wait_for_selector(".li-item", timeout=10_000)
    await page.wait_for_timeout(500)
    items = await page.query_selector_all(".li-item")
    result: list[dict] = []
    for item in items:
        name_el = await item.query_selector(".title-con")
        num_el = await item.query_selector(".num-value")
        name = (await name_el.text_content()).strip() if name_el else ""
        num = (await num_el.text_content()).strip() if num_el else "0/0"
        if name:
            result.append({"name": name, "completed": num, "element": item})
    return result


async def click_week(page, week: str) -> None:
    """点击周标签"""
    await page.evaluate(f"""
        () => {{
            const spans = document.querySelectorAll('span');
            for (const s of spans) {{
                if (s.textContent.trim() === '{week}') {{ s.click(); return; }}
            }}
        }}
    """)
    await page.wait_for_timeout(1000)


async def get_code_page(ctx):
    """从浏览器上下文中找到代码页面"""
    for p in ctx.pages:
        if "/class/code" in p.url:
            return p
    return None


async def get_detail_page(ctx):
    """从浏览器上下文中找到实训详情页面"""
    for p in ctx.pages:
        if "/class/combat/detail" in p.url:
            return p
    return None


async def close_extra_pages(ctx, keep_page) -> None:
    """关闭代码和详情页，回到课堂列表"""
    for p in ctx.pages[:]:
        if p != keep_page and ("/class/code" in p.url or "/class/combat/detail" in p.url):
            await p.close()
    await keep_page.bring_to_front()
    await keep_page.wait_for_timeout(1000)
    await keep_page.wait_for_selector(".li-item", timeout=10_000)
    await keep_page.wait_for_timeout(500)


async def extract_one_experiment(page, ctx, exp_name: str, logger) -> dict | None:
    """
    提取一个实验的所有答案。

    返回:
        {"type": "code", "quiz": {}, "code_levels": [...]} 或 None
    """
    # 重新定位实验并点击「开始实验」
    exps = await scan_experiments(page)
    target = next((e for e in exps if e["name"] == exp_name), None)
    if not target:
        logger.error(f"    未找到实验: {exp_name}")
        return None

    btn = await target["element"].query_selector("button:has-text('开始实验')")
    if not btn:
        logger.error(f"    未找到「开始实验」按钮")
        return None
    await btn.click()
    await page.wait_for_timeout(4000)

    detail = get_detail_page(ctx)
    if not detail:
        logger.error("    未找到详情页")
        return None
    await detail.bring_to_front()
    await detail.wait_for_load_state("networkidle")
    await detail.wait_for_timeout(2000)

    # 读取关卡表确认有未完成关卡
    levels = await read_combat_levels(detail)
    logger.info(f"    共 {len(levels)} 关")

    # 点击「进入实验」
    enter = await detail.query_selector("button:has-text('进入实验')")
    if not enter:
        logger.error("    未找到「进入实验」按钮")
        return None
    await enter.click()
    await detail.wait_for_timeout(4000)

    code_page = get_code_page(ctx) or (detail if "/class/code" in detail.url else None)
    if not code_page:
        logger.error("    未找到代码页面")
        return None
    await code_page.bring_to_front()
    await code_page.wait_for_timeout(2000)

    # 提取答案
    result = await extract_all_answers(code_page, logger, page_type="auto")
    await screenshot(code_page, f"extracted_{exp_name}", logger)

    await close_extra_pages(ctx, page)
    return result


async def main() -> None:
    args = parse_args()
    if args.headless:
        import config
        config.HEADLESS = True

    logger = setup_logging("pingtouge_build")
    logger.info("=" * 60)
    logger.info("平头哥实训平台 - 答案库构建器")
    logger.info("=" * 60)

    # 处理追加模式
    existing_bank: dict = {"experiments": {}}
    if args.append and os.path.exists(args.output):
        with open(args.output, "r", encoding="utf-8") as f:
            existing_bank = json.load(f)
        logger.info(f"追加模式: 已有 {len(existing_bank.get('experiments', {}))} 个实验")

    # 确定源账号
    source_account = args.account
    if not source_account:
        source_account = existing_bank.get("source_account", "")
    if not source_account:
        logger.error("请通过 --account 指定源账号，或确保已有 answer_bank.json 中包含 source_account")
        return

    logger.info(f"源账号: {source_account}")
    logger.info(f"课堂 URL: {args.classroom}")
    logger.info(f"输出文件: {args.output}")

    pw, browser = await launch_browser()

    try:
        ctx = await create_context(browser)
        page = await ctx.new_page()

        try:
            # 登录
            if not await login(page, source_account, args.password, logger):
                logger.error(f"登录失败: {source_account}")
                return

            # 进入课堂
            await page.goto(args.classroom, wait_until="networkidle", timeout=60_000)
            await page.wait_for_timeout(3000)
            await page.wait_for_selector(".li-item", timeout=15_000)
            await page.wait_for_timeout(2000)

            weeks = await get_weeks(page)
            logger.info(f"扫描到 {len(weeks)} 周: {weeks}")

            bank = {
                "source_account": source_account,
                "classroom_url": args.classroom,
                "experiments": existing_bank.get("experiments", {}),
            }
            total_extracted = 0

            for week in weeks:
                await click_week(page, week)
                exps = await scan_experiments(page)

                # 如果实验名为空，刷新重试
                if exps and not exps[0]["name"]:
                    logger.warning(f"  {week}: 实验名异常，刷新页面...")
                    await page.reload(wait_until="networkidle")
                    await page.wait_for_timeout(3000)
                    await click_week(page, week)
                    exps = await scan_experiments(page)

                logger.info(f"\n{week}: {len(exps)} 个实验")

                for exp in exps:
                    # 追加模式下跳过已有的
                    if args.append and exp["name"] in bank["experiments"]:
                        logger.info(f"  跳过 [{exp['name']}] (已在答案库中)")
                        continue

                    parts = exp["completed"].split("/")
                    is_done = len(parts) == 2 and parts[0] == parts[1]
                    status = "已完成" if is_done else "未完成"
                    logger.info(f"  提取 [{exp['name']}] ({status})")

                    result = await extract_one_experiment(page, ctx, exp["name"], logger)
                    if result:
                        bank["experiments"][exp["name"]] = result
                        total_extracted += 1
                        logger.info(f"    ✓ 提取成功: {len(result.get('code_levels', []))} 关代码, "
                                     f"{len(result.get('quiz', {}))} 题单选")
                    else:
                        logger.error(f"    ✗ 提取失败")

                    # 回到周列表
                    await click_week(page, week)

            # 保存
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(bank, f, ensure_ascii=False, indent=2)
            logger.info(f"\n{'=' * 60}")
            logger.info(f"完成! 共提取 {total_extracted} 个实验 → {args.output}")
            logger.info(f"{'=' * 60}")

        finally:
            await close_context(ctx)

    finally:
        await browser.close()
        await pw.stop()
        logger.info("\n全部完成")


if __name__ == "__main__":
    asyncio.run(main())
