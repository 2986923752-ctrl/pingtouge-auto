# 平头哥实训平台 - 作业答案自动填入

将已完成的作业答案，批量自动填入到其他账号的对应作业中。

支持**单选题**和**编程实训题（代码题）**，基于 Playwright 自动化操作浏览器。

## 工作流程

```
┌─────────────────────────────────────────────────┐
│  第一步: 构建答案库                               │
│  main_build.py                                  │
│  登录源账号 → 遍历所有实验 → 提取答案             │
│              ↓                                  │
│         answer_bank.json                        │
└─────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────┐
│  第二步: 批量填入                                 │
│  main.py                                        │
│  读取 accounts.xlsx → 逐个登录目标账号            │
│  → 对照 answer_bank.json 填入答案 → 评测         │
└─────────────────────────────────────────────────┘
```

**设计理念**: 答案库与填入分离。只需在一个源账号上构建一次答案库，即可反复用于多个目标账号。

## 环境要求

- Python 3.9+
- macOS / Linux / Windows

## 安装

```bash
# 1. 克隆项目
git clone <repo-url>
cd pingtouge_auto

# 2. 创建虚拟环境（推荐）
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 安装 Chromium 浏览器（Playwright 需要）
playwright install chromium
```

## 配置

编辑 `config.py` 修改以下配置：

```python
# 平台地址（根据实际情况修改）
BASE_URL = "http://keepctf.com:32716"

# 课堂 URL（在浏览器中打开课堂，复制地址栏 URL）
CLASSROOM_URL = "http://keepctf.com:32716/#/class?id=450&key=combat"

# 目标账号的默认密码（所有目标账号使用同一密码）
DEFAULT_PASSWORD = "520hzsxy@#"

# 浏览器设置
HEADLESS = False   # True = 后台运行不弹窗
SLOW_MO = 100      # 操作间隔(ms)，网络慢可调大
```

### 准备目标账号 Excel

创建 `accounts.xlsx`，只需一列：

| 目标账号 |
|---------|
| 2514190101 |
| 2514190102 |
| 2514190103 |

> 密码统一在 `config.py` 的 `DEFAULT_PASSWORD` 中配置。

## 使用

### 第一步：构建答案库

在一台**已完成所有作业**的源账号上运行，提取答案保存到 `answer_bank.json`。

```bash
# 基本用法
python main_build.py --account 2514190113 --password 你的密码

# 指定课堂 URL
python main_build.py --account 2514190113 --classroom "http://keepctf.com:32716/#/class?id=449&key=combat"

# 无头模式（后台运行）
python main_build.py --account 2514190113 --headless

# 追加模式（合并到已有答案库，不覆盖已提取的实验）
python main_build.py --account 2514190113 --append

# 指定输出文件
python main_build.py --account 2514190113 --output my_bank.json
```

> **提示**: 如果源账号密码与 `DEFAULT_PASSWORD` 相同，可省略 `--password` 参数。

### 第二步：批量填入

使用构建好的 `answer_bank.json`，向所有目标账号填入答案。

```bash
# 基本用法（使用默认 answer_bank.json 和 accounts.xlsx）
python main.py

# 预览模式（不实际填入，查看哪些实验会被处理）
python main.py --dry-run

# 无头模式 + 仅填入不评测
python main.py --headless --no-submit

# 仅处理指定周
python main.py --weeks 4,5

# 使用自定义答案库
python main.py --bank my_bank.json

# 查看版本
python main.py --version
```

## 项目结构

```
pingtouge_auto/
├── main.py              # 批量填入主入口（从答案库填入目标账号）
├── main_build.py        # 答案库构建器（从源账号提取答案）
├── config.py            # 配置文件（URL、超时、密码等）
├── browser.py           # 浏览器管理（启动、登录、导航）
├── extractor.py         # 答案提取器（单选 + CodeMirror 代码）
├── filler.py            # 答案填充器（填入 + 评测验证）
├── adapter_base.py      # 平台适配器基类（可扩展新平台）
├── adapter_pingtouge.py # 平头哥平台适配器实现
├── utils.py             # 工具函数（日志、重试、截图）
├── requirements.txt     # Python 依赖
├── accounts.xlsx        # 目标账号列表（需自行创建）
├── answer_bank.json     # 答案库（由 main_build.py 生成）
├── logs/                # 日志和截图输出目录
└── README.md
```

## 命令行参数参考

### main_build.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--account` | 源账号 | 必填（或从已有 answer_bank.json 读取） |
| `--password` | 源账号密码 | config.py 中的 DEFAULT_PASSWORD |
| `--classroom` | 课堂 URL | config.py 中的 CLASSROOM_URL |
| `--output` | 输出文件路径 | answer_bank.json |
| `--append` | 追加模式，不覆盖已有实验 | 关闭 |
| `--headless` | 无头模式 | 关闭 |

### main.py

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--bank` | 答案库 JSON 文件 | answer_bank.json |
| `--excel` | 账号 Excel 文件 | accounts.xlsx |
| `--weeks` | 指定周（逗号分隔） | 全部 |
| `--classroom` | 课堂 URL | config.py 中的 CLASSROOM_URL |
| `--dry-run` | 仅预览不填入 | 关闭 |
| `--headless` | 无头模式 | 关闭 |
| `--no-submit` | 填入但不评测 | 关闭 |
| `--version` | 显示版本号 | - |

## 适配其他平台

本项目采用**平台适配器架构**，核心自动化流程（登录→提取→构建答案库→多账号填入→评测）与具体平台解耦。

### 已支持平台

| 平台 | 适配器 | 特征 |
|------|--------|------|
| 平头哥实训 | `adapter_pingtouge.py` | CodeMirror 6 + Element UI + 关卡制 |

### 如何适配新平台

只需继承 `PlatformAdapter` 基类，实现约 **15 个方法**，即可复用全部自动化能力：

1. **创建适配器文件**，如 `adapter_zhihuishu.py`
2. **实现提取接口**：`extract_code()` / `extract_quiz_answers()` — 告诉脚本如何从页面提取答案
3. **实现填入接口**：`fill_code()` / `fill_quiz_answer()` — 告诉脚本如何填入答案
4. **实现导航接口**：`has_next_level()` / `click_next_level()` / `click_submit()` — 告诉脚本如何操作页面
5. **注册适配器**：加一行 `@register_adapter("your_platform")`
6. **配置平台 URL** 和选择器，即可运行

```python
# 示例：适配智慧树/超星/中国大学MOOC 只需这样
from adapter_base import PlatformAdapter, register_adapter

@register_adapter("zhihuishu")
class ZhihuishuAdapter(PlatformAdapter):
    platform_name = "智慧树"

    async def extract_code(self, page, logger) -> str:
        # 智慧树用 Monaco Editor，不是 CodeMirror
        return await page.evaluate("monaco.editor.getModels()[0].getValue()")

    async def detect_page_type(self, page) -> str:
        # 智慧树的页面结构不同
        ...
```

**本质上是同一套自动化理念**——只是每家的编辑器组件和按钮文本不一样。

## 常见问题

### Q: 登录失败？
- 检查账号密码是否正确
- 确认平台地址 `BASE_URL` 可以正常访问
- 查看 `logs/` 中的登录失败截图

### Q: 填入的代码不正确？
- 先用 `--dry-run` 确认流程正常
- 调大 `config.py` 中的 `SLOW_MO` 值（如 300-500）减慢操作速度
- 查看 `logs/screenshots/` 中的截图定位问题

### Q: 某些实验被跳过？
- 实验在目标账号上已全部完成 → 自动跳过
- 答案库中没有该实验 → 运行 `main_build.py --append` 补充提取
- 页面加载不完整 → 脚本会自动刷新重试

### Q: 平台页面结构变了？
选择器集中在各模块顶部，搜索 `.cm-editor`、`.li-item`、`button:has-text('评测')` 等关键选择器即可定位修改点。

## 注意事项

- 请确保你拥有所有操作账号的合法使用权
- 建议先用 `main.py --dry-run` 预览确认流程正常
- 答案库 (`answer_bank.json`) 包含完整代码答案，请勿公开分享
- 平台页面结构变化可能导致脚本失效，届时需更新选择器

## License

MIT License - 详见 [LICENSE](LICENSE)
