from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
XHS_SERVER = "http://127.0.0.1:11901"
LOCAL_CHROME_PATH = ""   # change me necessary！ for example C:/Program Files/Google/Chrome/Application/chrome.exe
LOCAL_CHROME_HEADLESS = False

# =========================
# App auth (后台登录) 配置
# =========================
# 生产环境建议通过环境变量注入这些值，避免明文落库/入仓库：
#
# APP_SECRET_KEY=your-strong-random-secret
# ADMIN_USERNAME=admin
# ADMIN_PASSWORD=change-me
# ACCESS_TOKEN_EXPIRES_IN=604800   # 7 days
#
# 注意：conf.py（真实运行配置）已在 .gitignore 中忽略，请不要把真实密码/secret 提交到仓库。
APP_SECRET_KEY = "change-me"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "change-me"
ACCESS_TOKEN_EXPIRES_IN = 604800  # 7 days
