import sqlite3
import json
import os

# 数据库文件路径（如果不存在会自动创建）
db_file = './database.db'

# 如果数据库已存在，则删除旧的表（可选）
# if os.path.exists(db_file):
#     os.remove(db_file)

# 连接到SQLite数据库（如果文件不存在则会自动创建）
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# 创建账号记录表
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type INTEGER NOT NULL,
    filePath TEXT NOT NULL,  -- 存储文件路径
    userName TEXT NOT NULL,
    status INTEGER DEFAULT 0
)
''')

# 创建文件记录表
cursor.execute('''CREATE TABLE IF NOT EXISTS file_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 唯一标识每条记录
    filename TEXT NOT NULL,               -- 文件名
    filesize REAL,                     -- 文件大小（单位：MB）
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP, -- 上传时间，默认当前时间
    file_path TEXT                        -- 文件路径
)
''')


# 创建后台登录用户表
cursor.execute('''
CREATE TABLE IF NOT EXISTS app_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login_at DATETIME
)
''')

# 发布任务表（用于 Data 页统计/日志）
cursor.execute('''
CREATE TABLE IF NOT EXISTS publish_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    platform_type INTEGER NOT NULL,
    title TEXT,
    tags_json TEXT,
    enable_timer INTEGER DEFAULT 0,
    videos_per_day INTEGER DEFAULT 1,
    daily_times_json TEXT,
    start_days INTEGER DEFAULT 0,
    product_link TEXT,
    product_title TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'created',
    error_msg TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS publish_task_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    account_file_path TEXT NOT NULL,
    scheduled_at DATETIME,
    started_at DATETIME,
    finished_at DATETIME,
    status TEXT DEFAULT 'pending',
    result_msg TEXT
)
''')

# 提交更改
conn.commit()
print("✅ 表创建成功")
# 关闭连接
conn.close()