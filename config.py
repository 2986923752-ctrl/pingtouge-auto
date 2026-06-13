"""
平头哥实训平台 - 配置文件
修改此文件以适配你的环境
"""

# ============================================
# 版本
# ============================================
__version__ = "1.0.0"

# ============================================
# 平台 URL
# ============================================
BASE_URL = "http://keepctf.com:32716"
LOGIN_URL = f"{BASE_URL}/#/login"

# ============================================
# Excel 账号文件（用于批量填入）
# ============================================
EXCEL_PATH = "accounts.xlsx"
EXCEL_COL_TARGET_ACCOUNT = "目标账号"     # 只需要这一列
DEFAULT_PASSWORD = "520hzsxy@#"           # 默认密码（所有账号统一）
CLASSROOM_URL = "http://keepctf.com:32716/#/class?id=450&key=combat"  # 默认课堂

# 以下已废弃（答案库已构建好，不再需要源账号列）
EXCEL_COL_SOURCE_ACCOUNT = "源账号"
EXCEL_COL_SOURCE_PASSWORD = "源密码"
EXCEL_COL_TARGET_PASSWORD = "目标密码"
EXCEL_COL_ASSIGNMENT_URL = "作业URL"

# 答案库文件
ANSWER_BANK_PATH = "answer_bank.json"

# ============================================
# 超时与重试（单位：毫秒）
# ============================================
DEFAULT_TIMEOUT = 30_000          # 元素等待超时
PAGE_LOAD_TIMEOUT = 60_000        # 页面加载超时
LOGIN_TIMEOUT = 15_000            # 登录响应超时
MAX_RETRIES = 3                   # 操作失败最大重试次数
RETRY_DELAY = 5_000               # 重试间隔（毫秒）
ACCOUNT_SWITCH_DELAY = 2_000      # 切换账号后的冷却等待

# ============================================
# 浏览器设置
# ============================================
HEADLESS = False                  # True = 无头模式（后台运行），False = 可见浏览器
SLOW_MO = 100                     # 操作间延迟（毫秒），0=最快，建议调试时设100-300
VIEWPORT_WIDTH = 1920
VIEWPORT_HEIGHT = 1080

# ============================================
# 日志
# ============================================
LOG_DIR = "logs"
LOG_LEVEL = "INFO"                # DEBUG / INFO / WARNING / ERROR
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"

# ============================================
# 调试选项
# ============================================
SAVE_SCREENSHOTS = True           # 出错时自动截图
SCREENSHOT_DIR = "logs/screenshots"
