"""
平台适配器基类 - 定义通用的在线教育平台自动化接口

适配新平台只需继承此类，实现各方法即可复用全部自动化流程：
  答案提取 → 答案库构建 → 多账号批量填入 → 评测验证

已实现适配器: PingtougeAdapter (平头哥实训平台)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Experiment:
    """通用实验/作业数据结构"""
    name: str                          # 实验名称
    type: str = "code"                 # "code" | "quiz" | "mixed"
    code_levels: list[dict] = field(default_factory=list)   # [{name, code}, ...]
    quiz_answers: dict[str, str | None] = field(default_factory=dict)  # {q_id: value}


@dataclass
class LevelStatus:
    """关卡状态"""
    name: str
    status: str                        # "已提交" | "未提交" | ...
    my_score: str = ""
    max_score: str = ""


class PlatformAdapter(ABC):
    """
    在线教育平台适配器基类。

    所有方法都是 Playwright Page 粒度的操作，适配器只关心：
      - 如何从页面提取答案
      - 如何向页面填入答案
      - 如何导航（上一关/下一关/进入实验）

    流程编排（登录、遍历实验、批量处理）完全复用，无需重复编写。
    """

    # ─── 元信息 ───

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台名称，用于日志"""
        ...

    # ─── 页面类型检测 ───

    @abstractmethod
    async def detect_page_type(self, page) -> str:
        """
        检测当前页面类型。

        返回: "code" | "quiz" | "mixed"
        """
        ...

    # ─── 答案提取 ───

    @abstractmethod
    async def extract_code(self, page, logger) -> str:
        """从代码编辑器提取完整代码"""
        ...

    @abstractmethod
    async def extract_quiz_answers(self, page, logger) -> dict[str, str | None]:
        """提取单选题答案，返回 {题号: 选项值}"""
        ...

    @abstractmethod
    async def get_current_level_name(self, page) -> str:
        """获取当前关卡名称"""
        ...

    @abstractmethod
    async def has_next_level(self, page) -> bool:
        """是否有下一关"""
        ...

    @abstractmethod
    async def click_next_level(self, page, logger) -> bool:
        """点击下一关，返回是否成功"""
        ...

    @abstractmethod
    async def read_levels_table(self, page) -> list[LevelStatus]:
        """读取关卡状态表（从实验详情页）"""
        ...

    # ─── 答案填入 ───

    @abstractmethod
    async def fill_code(self, page, code: str, logger) -> bool:
        """将代码填入编辑器，返回是否成功"""
        ...

    @abstractmethod
    async def fill_quiz_answer(self, page, q_id: str, value: str, logger) -> bool:
        """填入单个单选题答案"""
        ...

    @abstractmethod
    async def click_submit(self, page, logger) -> bool:
        """点击提交/评测按钮"""
        ...

    @abstractmethod
    async def check_result(self, page, logger) -> bool:
        """检查评测结果是否通过"""
        ...

    # ─── 实验导航（可选重写） ───

    @abstractmethod
    async def click_start_experiment(self, page, exp_name: str, logger) -> bool:
        """从实验列表点击「开始实验」"""
        ...

    @abstractmethod
    async def enter_code_page(self, ctx, logger):
        """
        进入代码编辑页面。

        返回: (page, detail_page)
        """
        ...

    # ─── 通用工具（可选重写） ───

    async def clear_editor(self, page, logger) -> bool:
        """清空编辑器（默认 Ctrl+A → Backspace）"""
        try:
            is_mac: bool = await page.evaluate(
                "() => navigator.platform.includes('Mac')"
            )
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
        except Exception:
            return False


# ─── 适配器注册表 ───

_ADAPTER_REGISTRY: dict[str, type[PlatformAdapter]] = {}


def register_adapter(name: str):
    """装饰器：注册平台适配器"""
    def decorator(cls: type[PlatformAdapter]):
        _ADAPTER_REGISTRY[name] = cls
        return cls
    return decorator


def get_adapter(name: str) -> type[PlatformAdapter] | None:
    """获取已注册的适配器类"""
    return _ADAPTER_REGISTRY.get(name)


def list_adapters() -> list[str]:
    """列出所有已注册的适配器"""
    return list(_ADAPTER_REGISTRY.keys())
