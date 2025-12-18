import asyncio
import base64
import datetime as dt
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from queue import Queue
from typing import Any, Dict, Optional, Tuple

from flask_cors import CORS
from myUtils.auth import check_cookie
from flask import Flask, Response, g, jsonify, request, send_from_directory
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from conf import ACCESS_TOKEN_EXPIRES_IN, ADMIN_PASSWORD, ADMIN_USERNAME, APP_SECRET_KEY, BASE_DIR
from myUtils.login import get_tencent_cookie, douyin_cookie_gen, get_ks_cookie, xiaohongshu_cookie_gen
from myUtils.postVideo import post_video_tencent, post_video_DouYin, post_video_ks, post_video_xhs

active_queues = {}
app = Flask(__name__)
app.config["SECRET_KEY"] = APP_SECRET_KEY

#允许所有来源跨域访问
CORS(app)

# 限制上传文件大小为160MB
app.config['MAX_CONTENT_LENGTH'] = 160 * 1024 * 1024

# 获取当前目录（假设 index.html 和 assets 在这里）
current_dir = os.path.dirname(os.path.abspath(__file__))

DB_PATH = Path(BASE_DIR / "db" / "database.db")


def api_response(*, code: int, msg: Optional[str], data: Any, http_status: int):
    return jsonify({"code": code, "msg": msg, "data": data}), http_status


def ok(data: Any = None, msg: Optional[str] = None):
    return api_response(code=200, msg=msg, data=data, http_status=200)


def fail(code: int, msg: str, http_status: Optional[int] = None):
    return api_response(code=code, msg=msg, data=None, http_status=http_status or code)


def _db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    """Ensure required tables exist (idempotent)."""
    with _db_connect() as conn:
        cur = conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS user_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type INTEGER NOT NULL,
                filePath TEXT NOT NULL,
                userName TEXT NOT NULL,
                status INTEGER DEFAULT 0
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS file_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                filesize REAL,
                upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_login_at DATETIME
            )
            """
        )

        # publish tables are created here too (so backend works even if createTable.py wasn't run)
        cur.execute(
            """
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
            """
        )
        cur.execute(
            """
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
            """
        )

        conn.commit()


def _now_iso():
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def normalize_daily_times(daily_times):
    """
    Frontend may send ['10:00', '18:30'] while scheduler expects hour integers.
    Returns a list of hours like [10, 18].
    """
    if daily_times is None:
        return None
    out = []
    for t in daily_times:
        if isinstance(t, int):
            out.append(t)
        elif isinstance(t, str):
            try:
                out.append(int(t.split(":", 1)[0]))
            except Exception:
                continue
    return out or None


def hash_password(password: str, *, iterations: int = 200_000) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return "pbkdf2_sha256${}${}${}".format(
        iterations,
        base64.b64encode(salt).decode("utf-8"),
        base64.b64encode(dk).decode("utf-8"),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters_s, salt_b64, dk_b64 = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iters = int(iters_s)
        salt = base64.b64decode(salt_b64.encode("utf-8"))
        dk_expected = base64.b64decode(dk_b64.encode("utf-8"))
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
        return hmac.compare_digest(dk, dk_expected)
    except Exception:
        return False


_token_serializer = URLSafeTimedSerializer(APP_SECRET_KEY, salt="access-token-v1")


def issue_access_token(payload: Dict[str, Any]) -> str:
    return _token_serializer.dumps(payload)


def verify_access_token(token: str) -> Dict[str, Any]:
    return _token_serializer.loads(token, max_age=ACCESS_TOKEN_EXPIRES_IN)


def get_token_from_request() -> Optional[str]:
    auth = request.headers.get("Authorization", "")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    # For EventSource / <video> / <a download> etc. where headers are hard:
    return request.args.get("token") or request.args.get("access_token")


def require_auth():
    token = get_token_from_request()
    if not token:
        return None, fail(401, "Unauthorized", 401)

    try:
        payload = verify_access_token(token)
    except SignatureExpired:
        return None, fail(401, "Token expired", 401)
    except BadSignature:
        return None, fail(401, "Invalid token", 401)
    except Exception:
        return None, fail(401, "Unauthorized", 401)

    # Ensure user still exists
    uid = payload.get("uid")
    if not uid:
        return None, fail(401, "Invalid token", 401)

    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, username, role, created_at, last_login_at FROM app_users WHERE id = ?", (uid,))
        row = cur.fetchone()
        if not row:
            return None, fail(401, "User not found", 401)

        user = dict(row)
        g.current_user = user
        return user, None


@app.before_request
def _bootstrap_and_auth_guard():
    ensure_tables()

    # allow CORS preflight
    if request.method == "OPTIONS":
        return None

    path = request.path or "/"

    # public allowlist
    if path in ("/", "/favicon.ico", "/vite.svg"):
        return None
    if path.startswith("/assets/"):
        return None
    if path in ("/auth/login", "/auth/register"):
        return None

    # all other endpoints require login
    _, err = require_auth()
    return err

# 处理所有静态资源请求（未来打包用）
@app.route('/assets/<filename>')
def custom_static(filename):
    return send_from_directory(os.path.join(current_dir, 'assets'), filename)

# 处理 favicon.ico 静态资源（未来打包用）
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(current_dir, 'assets'), 'vite.svg')

@app.route('/vite.svg')
def vite_svg():
    return send_from_directory(os.path.join(current_dir, 'assets'), 'vite.svg')

# （未来打包用）
@app.route('/')
def index():  # put application's code here
    return send_from_directory(current_dir, 'index.html')


@app.route("/auth/register", methods=["POST"])
def auth_register():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    # If request body is empty, allow bootstrapping from conf (handy for first run)
    if not username and not password:
        username = (ADMIN_USERNAME or "").strip()
        password = ADMIN_PASSWORD or ""

    if not username or not password:
        return fail(400, "username/password required", 400)

    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(1) AS c FROM app_users")
        has_any = (cur.fetchone()["c"] or 0) > 0

        if has_any:
            # Only admin can create more users
            user, err = require_auth()
            if err:
                return err
            if (user.get("role") or "") != "admin":
                return fail(403, "Forbidden", 403)
            role = payload.get("role") or "user"
        else:
            role = "admin"

        try:
            cur.execute(
                "INSERT INTO app_users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username, hash_password(password), role, _now_iso()),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            return fail(409, "Username already exists", 409)

    return ok({"username": username, "role": role}, "registered")


@app.route("/auth/login", methods=["POST"])
def auth_login():
    payload = request.get_json(silent=True) or {}
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        return fail(400, "username/password required", 400)

    with _db_connect() as conn:
        cur = conn.cursor()
        # bootstrap: if no users exist, allow logging in with conf admin to auto-create the first admin
        cur.execute("SELECT COUNT(1) AS c FROM app_users")
        user_count = int(cur.fetchone()["c"] or 0)
        if user_count == 0:
            if username == (ADMIN_USERNAME or "").strip() and password == (ADMIN_PASSWORD or ""):
                cur.execute(
                    "INSERT INTO app_users (username, password_hash, role, created_at, last_login_at) VALUES (?, ?, ?, ?, ?)",
                    (username, hash_password(password), "admin", _now_iso(), _now_iso()),
                )
                conn.commit()
            else:
                return fail(401, "No users yet. Use configured admin credentials or call /auth/register first.", 401)

        cur.execute("SELECT * FROM app_users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row:
            return fail(401, "Invalid username or password", 401)

        user = dict(row)
        if not verify_password(password, user.get("password_hash") or ""):
            return fail(401, "Invalid username or password", 401)

        cur.execute("UPDATE app_users SET last_login_at = ? WHERE id = ?", (_now_iso(), user["id"]))
        conn.commit()

    token = issue_access_token({"uid": user["id"], "username": user["username"], "role": user["role"]})
    return ok(
        {
            "access_token": token,
            "expires_in": ACCESS_TOKEN_EXPIRES_IN,
            "user": {"id": user["id"], "username": user["username"], "role": user["role"]},
        },
        "login success",
    )


@app.route("/auth/me", methods=["GET"])
def auth_me():
    user, err = require_auth()
    if err:
        return err
    return ok(user, None)


@app.route("/auth/logout", methods=["POST"])
def auth_logout():
    # Stateless token; FE just deletes token locally
    return ok(None, "logout success")

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return fail(400, "No file part in the request", 400)
    file = request.files['file']
    if file.filename == '':
        return fail(400, "No selected file", 400)
    try:
        # 保存文件到指定位置
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")
        filepath = Path(BASE_DIR / "videoFile" / f"{uuid_v1}_{file.filename}")
        file.save(filepath)
        return ok(f"{uuid_v1}_{file.filename}", "File uploaded successfully")
    except Exception as e:
        return fail(500, str(e), 500)

@app.route('/getFile', methods=['GET'])
def get_file():
    # 获取 filename 参数
    filename = request.args.get('filename')

    if not filename:
        return fail(400, "filename is required", 400)

    # 防止路径穿越攻击
    if '..' in filename or filename.startswith('/'):
        return fail(400, "Invalid filename", 400)

    # 拼接完整路径
    file_path = str(Path(BASE_DIR / "videoFile"))

    # 返回文件
    return send_from_directory(file_path,filename)


@app.route("/download/<path:filename>", methods=["GET"])
def download_file(filename: str):
    """
    Download a material from videoFile.
    Note: Auth is enforced globally via before_request; for browser downloads use ?token=...
    """
    if not filename:
        return fail(400, "filename is required", 400)
    # Prevent path traversal
    if ".." in filename or filename.startswith("/"):
        return fail(400, "Invalid filename", 400)

    file_dir = str(Path(BASE_DIR / "videoFile"))
    return send_from_directory(file_dir, filename, as_attachment=True)


@app.route('/uploadSave', methods=['POST'])
def upload_save():
    if 'file' not in request.files:
        return fail(400, "No file part in the request", 400)

    file = request.files['file']
    if file.filename == '':
        return fail(400, "No selected file", 400)

    # 获取表单中的自定义文件名（可选）
    custom_filename = request.form.get('filename', None)
    if custom_filename:
        filename = custom_filename + "." + file.filename.split('.')[-1]
    else:
        filename = file.filename

    try:
        # 生成 UUID v1
        uuid_v1 = uuid.uuid1()
        print(f"UUID v1: {uuid_v1}")

        # 构造文件名和路径
        final_filename = f"{uuid_v1}_{filename}"
        filepath = Path(BASE_DIR / "videoFile" / f"{uuid_v1}_{filename}")

        # 保存文件
        file.save(filepath)

        with _db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                                INSERT INTO file_records (filename, filesize, file_path)
            VALUES (?, ?, ?)
                                ''', (filename, round(float(os.path.getsize(filepath)) / (1024 * 1024),2), final_filename))
            conn.commit()
            print("✅ 上传文件已记录")

        return ok({"filename": filename, "filepath": final_filename}, "File uploaded and saved successfully")

    except Exception as e:
        print(f"Upload failed: {e}")
        return fail(500, f"upload failed: {e}", 500)

@app.route('/getFiles', methods=['GET'])
def get_all_files():
    try:
        # 使用 with 自动管理数据库连接
        with _db_connect() as conn:
            cursor = conn.cursor()

            # 查询所有记录
            cursor.execute("SELECT * FROM file_records")
            rows = cursor.fetchall()

            # 将结果转为字典列表，并提取UUID
            data = []
            for row in rows:
                row_dict = dict(row)
                # 从 file_path 中提取 UUID (文件名的第一部分，下划线前)
                if row_dict.get('file_path'):
                    file_path_parts = row_dict['file_path'].split('_', 1)  # 只分割第一个下划线
                    if len(file_path_parts) > 0:
                        row_dict['uuid'] = file_path_parts[0]  # UUID 部分
                    else:
                        row_dict['uuid'] = ''
                else:
                    row_dict['uuid'] = ''
                data.append(row_dict)

            return ok(data, "success")
    except Exception as e:
        return fail(500, "get file failed!", 500)


@app.route("/getAccounts", methods=['GET'])
def getAccounts():
    """快速获取所有账号信息，不进行cookie验证"""
    try:
        with _db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT * FROM user_info''')
            rows = cursor.fetchall()
            rows_list = [list(row) for row in rows]

            print("\n📋 当前数据表内容（快速获取）：")
            for row in rows:
                print(row)

            return ok(rows_list, None)
    except Exception as e:
        print(f"获取账号列表时出错: {str(e)}")
        return fail(500, f"获取账号列表失败: {str(e)}", 500)


@app.route("/getValidAccounts",methods=['GET'])
async def getValidAccounts():
    with _db_connect() as conn:
        cursor = conn.cursor()
        cursor.execute('''
        SELECT * FROM user_info''')
        rows = cursor.fetchall()
        rows_list = [list(row) for row in rows]
        print("\n📋 当前数据表内容：")
        for row in rows:
            print(row)
        for row in rows_list:
            flag = await check_cookie(row[1],row[2])
            if not flag:
                row[4] = 0
                cursor.execute('''
                UPDATE user_info 
                SET status = ? 
                WHERE id = ?
                ''', (0,row[0]))
                conn.commit()
                print("✅ 用户状态已更新")
        for row in rows:
            print(row)
        return ok(rows_list, None)

@app.route('/deleteFile', methods=['GET'])
def delete_file():
    file_id = request.args.get('id')

    if not file_id or not file_id.isdigit():
        return fail(400, "Invalid or missing file ID", 400)

    try:
        # 获取数据库连接
        with _db_connect() as conn:
            cursor = conn.cursor()

            # 查询要删除的记录
            cursor.execute("SELECT * FROM file_records WHERE id = ?", (file_id,))
            record = cursor.fetchone()

            if not record:
                return fail(404, "File not found", 404)

            record = dict(record)

            # 获取文件路径并删除实际文件
            file_path = Path(BASE_DIR / "videoFile" / record['file_path'])
            if file_path.exists():
                try:
                    file_path.unlink()  # 删除文件
                    print(f"✅ 实际文件已删除: {file_path}")
                except Exception as e:
                    print(f"⚠️ 删除实际文件失败: {e}")
                    # 即使删除文件失败，也要继续删除数据库记录，避免数据不一致
            else:
                print(f"⚠️ 实际文件不存在: {file_path}")

            # 删除数据库记录
            cursor.execute("DELETE FROM file_records WHERE id = ?", (file_id,))
            conn.commit()

        return ok({"id": record["id"], "filename": record["filename"]}, "File deleted successfully")

    except Exception as e:
        return fail(500, "delete failed!", 500)

@app.route('/deleteAccount', methods=['GET'])
def delete_account():
    account_id = int(request.args.get('id'))

    try:
        # 获取数据库连接
        with _db_connect() as conn:
            cursor = conn.cursor()

            # 查询要删除的记录
            cursor.execute("SELECT * FROM user_info WHERE id = ?", (account_id,))
            record = cursor.fetchone()

            if not record:
                return fail(404, "account not found", 404)

            record = dict(record)

            # 删除数据库记录
            cursor.execute("DELETE FROM user_info WHERE id = ?", (account_id,))
            conn.commit()

        return ok(None, "account deleted successfully")

    except Exception as e:
        return fail(500, "delete failed!", 500)


# SSE 登录接口
@app.route('/login')
def login():
    # 1 小红书 2 视频号 3 抖音 4 快手
    type = request.args.get('type')
    # 账号名
    id = request.args.get('id')

    # 模拟一个用于异步通信的队列
    status_queue = Queue()
    active_queues[id] = status_queue

    def on_close():
        print(f"清理队列: {id}")
        del active_queues[id]
    # 启动异步任务线程
    thread = threading.Thread(target=run_async_function, args=(type,id,status_queue), daemon=True)
    thread.start()
    response = Response(sse_stream(status_queue,), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # 关键：禁用 Nginx 缓冲
    response.headers['Content-Type'] = 'text/event-stream'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/postVideo', methods=['POST'])
def postVideo():
    user = getattr(g, "current_user", None) or {}
    data = request.get_json(silent=True) or {}

    file_list = data.get("fileList", []) or []
    account_list = data.get("accountList", []) or []
    platform_type = data.get("type")
    title = data.get("title") or ""
    tags = data.get("tags") or []
    category = data.get("category")
    enableTimer = data.get("enableTimer") or 0

    if category == 0:
        category = None

    productLink = data.get("productLink", "") or ""
    productTitle = data.get("productTitle", "") or ""
    thumbnail_path = data.get("thumbnail", "") or ""
    is_draft = bool(data.get("isDraft", False))

    videos_per_day = data.get("videosPerDay") or 1
    daily_times = normalize_daily_times(data.get("dailyTimes"))
    start_days = data.get("startDays") or 0

    if not isinstance(file_list, list) or not file_list:
        return fail(400, "fileList is required", 400)
    if not isinstance(account_list, list) or not account_list:
        return fail(400, "accountList is required", 400)
    if platform_type not in (1, 2, 3, 4):
        return fail(400, "Invalid platform type", 400)

    # 计算每个文件的 scheduled_at（按文件维度，账号共享同一时刻）
    scheduled_by_file = [None] * len(file_list)
    if enableTimer:
        try:
            from utils.files_times import generate_schedule_time_next_day

            scheduled_by_file = generate_schedule_time_next_day(
                len(file_list), int(videos_per_day), daily_times, start_days=int(start_days)
            )
        except Exception as e:
            return fail(400, f"Invalid schedule params: {e}", 400)

    # 创建发布任务与明细
    task_id = None
    item_map = {}  # (file_path, account_file_path) -> item_id
    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO publish_tasks
              (user_id, platform_type, title, tags_json, enable_timer, videos_per_day, daily_times_json, start_days,
               product_link, product_title, created_at, status, error_msg)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.get("id"),
                int(platform_type),
                title,
                json.dumps(tags, ensure_ascii=False),
                int(bool(enableTimer)),
                int(videos_per_day),
                json.dumps(daily_times, ensure_ascii=False) if daily_times is not None else None,
                int(start_days),
                productLink,
                productTitle,
                _now_iso(),
                "running",
                None,
            ),
        )
        task_id = cur.lastrowid

        for idx, file_path in enumerate(file_list):
            scheduled_at = scheduled_by_file[idx] if enableTimer else None
            if isinstance(scheduled_at, dt.datetime):
                scheduled_at = scheduled_at.replace(microsecond=0).isoformat()
            else:
                scheduled_at = None

            for account_file_path in account_list:
                status = "scheduled" if scheduled_at else "pending"
                cur.execute(
                    """
                    INSERT INTO publish_task_items
                      (task_id, file_path, account_file_path, scheduled_at, started_at, finished_at, status, result_msg)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (task_id, str(file_path), str(account_file_path), scheduled_at, None, None, status, None),
                )
                item_map[(str(file_path), str(account_file_path))] = cur.lastrowid

        conn.commit()

    def reporter(file_path, account_file_path, status, scheduled_at=None, result_msg=None):
        item_id = item_map.get((str(file_path), str(account_file_path)))
        if not item_id:
            return

        now = _now_iso()
        with _db_connect() as conn:
            cur = conn.cursor()
            if status == "running":
                cur.execute(
                    "UPDATE publish_task_items SET status = ?, started_at = COALESCE(started_at, ?) WHERE id = ?",
                    ("running", now, item_id),
                )
            elif status in ("success", "failed"):
                cur.execute(
                    "UPDATE publish_task_items SET status = ?, finished_at = ?, result_msg = ? WHERE id = ?",
                    (status, now, result_msg, item_id),
                )
            else:
                cur.execute("UPDATE publish_task_items SET status = ?, result_msg = ? WHERE id = ?", (status, result_msg, item_id))
            conn.commit()

    # 执行发布（同步执行，沿用现有实现）
    try:
        if platform_type == 1:
            post_video_xhs(
                title,
                file_list,
                tags,
                account_list,
                category,
                bool(enableTimer),
                int(videos_per_day),
                daily_times,
                int(start_days),
                reporter=reporter,
            )
        elif platform_type == 2:
            post_video_tencent(
                title,
                file_list,
                tags,
                account_list,
                category,
                bool(enableTimer),
                int(videos_per_day),
                daily_times,
                int(start_days),
                is_draft,
                reporter=reporter,
            )
        elif platform_type == 3:
            post_video_DouYin(
                title,
                file_list,
                tags,
                account_list,
                category,
                bool(enableTimer),
                int(videos_per_day),
                daily_times,
                int(start_days),
                thumbnail_path,
                productLink,
                productTitle,
                reporter=reporter,
            )
        elif platform_type == 4:
            post_video_ks(
                title,
                file_list,
                tags,
                account_list,
                category,
                bool(enableTimer),
                int(videos_per_day),
                daily_times,
                int(start_days),
                reporter=reporter,
            )
    except Exception as e:
        with _db_connect() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE publish_tasks SET status = ?, error_msg = ? WHERE id = ?", ("failed", str(e), task_id))
            conn.commit()
        return fail(500, f"publish failed: {e}", 500)

    # 汇总任务状态
    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
              SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_cnt,
              SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_cnt,
              COUNT(1) AS total_cnt
            FROM publish_task_items
            WHERE task_id = ?
            """,
            (task_id,),
        )
        r = cur.fetchone()
        success_cnt = int(r["success_cnt"] or 0)
        failed_cnt = int(r["failed_cnt"] or 0)
        total_cnt = int(r["total_cnt"] or 0)
        final_status = "failed" if failed_cnt > 0 else "success"
        cur.execute("UPDATE publish_tasks SET status = ? WHERE id = ?", (final_status, task_id))
        conn.commit()

    return ok({"task_id": task_id, "total": total_cnt, "success": success_cnt, "failed": failed_cnt}, None)


@app.route('/updateUserinfo', methods=['POST'])
def updateUserinfo():
    # 获取JSON数据
    data = request.get_json()

    # 从JSON数据中提取 type 和 userName
    user_id = data.get('id')
    type = data.get('type')
    userName = data.get('userName')
    try:
        # 获取数据库连接
        with _db_connect() as conn:
            cursor = conn.cursor()

            # 更新数据库记录
            cursor.execute('''
                           UPDATE user_info
                           SET type     = ?,
                               userName = ?
                           WHERE id = ?;
                           ''', (type, userName, user_id))
            conn.commit()

        return ok(None, "account update successfully")

    except Exception as e:
        return fail(500, "update failed!", 500)

@app.route('/postVideoBatch', methods=['POST'])
def postVideoBatch():
    data_list = request.get_json()

    if not isinstance(data_list, list):
        return fail(400, "Expected a JSON array", 400)
    for data in data_list:
        # 从JSON数据中提取fileList和accountList
        file_list = data.get('fileList', [])
        account_list = data.get('accountList', [])
        type = data.get('type')
        title = data.get('title')
        tags = data.get('tags')
        category = data.get('category')
        enableTimer = data.get('enableTimer')
        if category == 0:
            category = None
        productLink = data.get('productLink', '')
        productTitle = data.get('productTitle', '')

        videos_per_day = data.get('videosPerDay')
        daily_times = data.get('dailyTimes')
        start_days = data.get('startDays')
        # 打印获取到的数据（仅作为示例）
        print("File List:", file_list)
        print("Account List:", account_list)
        if type == 2:
            post_video_tencent(
                title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times, start_days
            )
        elif type == 3:
            post_video_DouYin(
                title,
                file_list,
                tags,
                account_list,
                category,
                enableTimer,
                videos_per_day,
                daily_times,
                start_days,
                productLink,
                productTitle,
            )
        elif type == 4:
            post_video_ks(
                title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times, start_days
            )
        elif type == 1:
            # TODO: batch xhs if needed
            post_video_xhs(
                title, file_list, tags, account_list, category, enableTimer, videos_per_day, daily_times, start_days
            )
        else:
            return fail(400, "Invalid platform type", 400)

    return ok(None, None)

# Cookie文件上传API
@app.route('/uploadCookie', methods=['POST'])
def upload_cookie():
    try:
        if 'file' not in request.files:
            return fail(400, "没有找到Cookie文件", 400)

        file = request.files['file']
        if file.filename == '':
            return fail(400, "Cookie文件名不能为空", 400)

        if not file.filename.endswith('.json'):
            return fail(400, "Cookie文件必须是JSON格式", 400)

        # 获取账号信息
        account_id = request.form.get('id')
        platform = request.form.get('platform')

        if not account_id or not platform:
            return fail(400, "缺少账号ID或平台信息", 400)

        # 从数据库获取账号的文件路径
        with _db_connect() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT filePath FROM user_info WHERE id = ?', (account_id,))
            result = cursor.fetchone()

        if not result:
            return fail(404, "账号不存在", 404)

        # 保存上传的Cookie文件到对应路径
        cookie_file_path = Path(BASE_DIR / "cookiesFile" / result['filePath'])
        cookie_file_path.parent.mkdir(parents=True, exist_ok=True)

        file.save(str(cookie_file_path))

        # 更新数据库中的账号信息（可选，比如更新更新时间）
        # 这里可以根据需要添加额外的处理逻辑

        return ok(None, "Cookie文件上传成功")

    except Exception as e:
        print(f"上传Cookie文件时出错: {str(e)}")
        return fail(500, f"上传Cookie文件失败: {str(e)}", 500)


# Cookie文件下载API
@app.route('/downloadCookie', methods=['GET'])
def download_cookie():
    try:
        file_path = request.args.get('filePath')
        if not file_path:
            return fail(400, "缺少文件路径参数", 400)

        # 验证文件路径的安全性，防止路径遍历攻击
        cookie_file_path = Path(BASE_DIR / "cookiesFile" / file_path).resolve()
        base_path = Path(BASE_DIR / "cookiesFile").resolve()

        if not cookie_file_path.is_relative_to(base_path):
            return fail(400, "非法文件路径", 400)

        if not cookie_file_path.exists():
            return fail(404, "Cookie文件不存在", 404)

        # 返回文件
        return send_from_directory(
            directory=str(cookie_file_path.parent),
            path=cookie_file_path.name,
            as_attachment=True
        )

    except Exception as e:
        print(f"下载Cookie文件时出错: {str(e)}")
        return fail(500, f"下载Cookie文件失败: {str(e)}", 500)


@app.route("/publish_tasks", methods=["GET"])
def list_publish_tasks():
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", request.args.get("pageSize", 10)))
    platform_type = request.args.get("platform_type")
    status = request.args.get("status")
    keyword = (request.args.get("keyword") or "").strip()
    start_date = request.args.get("start_date")  # YYYY-MM-DD
    end_date = request.args.get("end_date")      # YYYY-MM-DD

    where = []
    params = []
    if platform_type:
        where.append("platform_type = ?")
        params.append(int(platform_type))
    if status:
        where.append("status = ?")
        params.append(status)
    if keyword:
        where.append("(title LIKE ? OR tags_json LIKE ?)")
        params.append(f"%{keyword}%")
        params.append(f"%{keyword}%")
    if start_date:
        where.append("substr(created_at, 1, 10) >= ?")
        params.append(start_date)
    if end_date:
        where.append("substr(created_at, 1, 10) <= ?")
        params.append(end_date)

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    offset = max(page - 1, 0) * page_size

    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(1) AS c FROM publish_tasks {where_sql}", params)
        total = int(cur.fetchone()["c"] or 0)

        cur.execute(
            f"""
            SELECT
              t.*,
              (SELECT COUNT(1) FROM publish_task_items i WHERE i.task_id = t.id) AS items_total,
              (SELECT SUM(CASE WHEN i.status='success' THEN 1 ELSE 0 END) FROM publish_task_items i WHERE i.task_id = t.id) AS items_success,
              (SELECT SUM(CASE WHEN i.status='failed' THEN 1 ELSE 0 END) FROM publish_task_items i WHERE i.task_id = t.id) AS items_failed
            FROM publish_tasks t
            {where_sql}
            ORDER BY t.id DESC
            LIMIT ? OFFSET ?
            """,
            params + [page_size, offset],
        )
        rows = [dict(r) for r in cur.fetchall()]

    return ok({"items": rows, "page": page, "page_size": page_size, "total": total}, None)


@app.route("/publish_tasks/<int:task_id>", methods=["GET"])
def get_publish_task(task_id: int):
    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM publish_tasks WHERE id = ?", (task_id,))
        task = cur.fetchone()
        if not task:
            return fail(404, "task not found", 404)

        cur.execute("SELECT * FROM publish_task_items WHERE task_id = ? ORDER BY id ASC", (task_id,))
        items = [dict(r) for r in cur.fetchall()]

    return ok({"task": dict(task), "items": items}, None)


@app.route("/stats/summary", methods=["GET"])
def stats_summary():
    with _db_connect() as conn:
        cur = conn.cursor()

        # accounts
        cur.execute("SELECT COUNT(1) AS total, SUM(CASE WHEN status = 1 THEN 1 ELSE 0 END) AS normal FROM user_info")
        acc = cur.fetchone()
        acc_total = int(acc["total"] or 0)
        acc_normal = int(acc["normal"] or 0)
        acc_abnormal = acc_total - acc_normal

        # materials
        cur.execute("SELECT COUNT(1) AS total, SUM(filesize) AS total_size_mb FROM file_records")
        mat = cur.fetchone()
        mat_total = int(mat["total"] or 0)
        mat_size = float(mat["total_size_mb"] or 0.0)

        # publish tasks/items
        cur.execute("SELECT COUNT(1) AS total, SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed FROM publish_tasks")
        pt = cur.fetchone()
        task_total = int(pt["total"] or 0)
        task_success = int(pt["success"] or 0)
        task_failed = int(pt["failed"] or 0)

        cur.execute("SELECT SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) AS success, SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed, SUM(CASE WHEN status='running' THEN 1 ELSE 0 END) AS running, SUM(CASE WHEN status='scheduled' THEN 1 ELSE 0 END) AS scheduled FROM publish_task_items")
        pi = cur.fetchone()
        item_stats = {
            "success": int(pi["success"] or 0),
            "failed": int(pi["failed"] or 0),
            "running": int(pi["running"] or 0),
            "scheduled": int(pi["scheduled"] or 0),
        }

    return ok(
        {
            "accounts": {"total": acc_total, "normal": acc_normal, "abnormal": acc_abnormal},
            "materials": {"total": mat_total, "total_size_mb": round(mat_size, 2)},
            "publish_tasks": {"total": task_total, "success": task_success, "failed": task_failed},
            "publish_items": item_stats,
        },
        None,
    )


@app.route("/stats/uploads_trend", methods=["GET"])
def stats_uploads_trend():
    days = int(request.args.get("days", 7))
    days = max(1, min(days, 365))
    with _db_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date(upload_time) AS day,
                   COUNT(1) AS upload_count,
                   SUM(filesize) AS upload_size_mb
            FROM file_records
            WHERE upload_time >= datetime('now', ?)
            GROUP BY date(upload_time)
            ORDER BY day ASC
            """,
            (f"-{days} day",),
        )
        rows = [
            {
                "day": r["day"],
                "upload_count": int(r["upload_count"] or 0),
                "upload_size_mb": round(float(r["upload_size_mb"] or 0.0), 2),
            }
            for r in cur.fetchall()
        ]

    return ok(rows, None)


# 包装函数：在线程中运行异步函数
def run_async_function(type,id,status_queue):
    if type == '1':
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(xiaohongshu_cookie_gen(id, status_queue))
        loop.close()
    elif type == '2':
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(get_tencent_cookie(id,status_queue))
        loop.close()
    elif type == '3':
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(douyin_cookie_gen(id,status_queue))
        loop.close()
    elif type == '4':
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(get_ks_cookie(id,status_queue))
        loop.close()
    else:
        status_queue.put("500")

# SSE 流生成器函数
def sse_stream(status_queue):
    while True:
        if not status_queue.empty():
            msg = status_queue.get()
            yield f"data: {msg}\n\n"
        else:
            # 避免 CPU 占满
            time.sleep(0.1)

if __name__ == '__main__':
    app.run(host='0.0.0.0' ,port=5409)
