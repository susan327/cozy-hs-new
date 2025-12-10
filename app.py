# app.py — cozy-hs / Neon(Postgres) 対応・休業日「毎週火曜＋第2/第3月曜」自動反映 完全版

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
import os
import json
import logging
import uuid
import calendar
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo
from werkzeug.utils import secure_filename

# --- DB: SQLAlchemy (Neon/Postgres 前提) ---
from flask_sqlalchemy import SQLAlchemy

# -----------------------------
# 基本設定
# -----------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "cozyhair-super-secret")

BASE_DIR = os.path.dirname(__file__)
UPLOAD_FOLDER = os.path.join("static", "uploads")
OVERRIDES_FILE = os.path.join("static", "holidays.json")   # 手動上書き（臨時休業）用
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
logging.basicConfig(level=logging.INFO)

# -----------------------------
# DB 初期化（Neon専用）
# -----------------------------
db = SQLAlchemy()

def _get_database_uri():
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is required (Neon-only mode). Set postgresql://USER:PASS@HOST/DB?sslmode=require"
        )
    if "sslmode" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    return url

app.config["SQLALCHEMY_DATABASE_URI"] = _get_database_uri()
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 5,
    "max_overflow": 5,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# -----------------------------
# モデル
# -----------------------------
class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    body = db.Column(db.Text, nullable=False)
    image = db.Column(db.Text)  # /static/uploads/<uuid>.<ext>
    # UTCで保存（tz付き）
    timestamp = db.Column(db.DateTime(timezone=True), nullable=False,
                          default=lambda: datetime.now(timezone.utc))

# -----------------------------
# ユーティリティ
# -----------------------------
def load_json(path: str):
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_json(data, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def now_utc_iso_z() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

@app.template_filter("to_jst")
def to_jst(dt_or_iso) -> str:
    if not dt_or_iso:
        return ""
    try:
        if isinstance(dt_or_iso, datetime):
            dtv = dt_or_iso
        else:
            dtv = datetime.fromisoformat(str(dt_or_iso).replace("Z", "+00:00"))
        return dtv.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y年%m月%d日 %H:%M")
    except Exception:
        return str(dt_or_iso)

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

def save_uploaded_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    if ext not in ALLOWED_EXTS:
        return None
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    unique_name = f"{uuid.uuid4().hex}{ext}"
    abs_path = os.path.join(UPLOAD_FOLDER, unique_name)
    file_storage.save(abs_path)
    return f"/static/uploads/{unique_name}"

# -----------------------------
# 休業日 自動生成ロジック
#   ルール:
#     - 毎週 火曜 (weekday=1)
#     - 第2・第3 月曜 (weekday=0)
#   返却形式:
#     { "YYYY-MM": ["YYYY-MM-DD", ...], ... }
# -----------------------------
def month_key(y: int, m: int) -> str:
    return f"{y:04d}-{m:02d}"

def all_days_in_month(y: int, m: int):
    last = calendar.monthrange(y, m)[1]
    for d in range(1, last + 1):
        yield date(y, m, d)

def nth_weekday_of_month(y: int, m: int, weekday: int, n: int):
    cnt = 0
    for d in all_days_in_month(y, m):
        if d.weekday() == weekday:
            cnt += 1
            if cnt == n:
                return d
    return None

def generate_rule_based_closed_map(start_date: date, months: int = 2):
    """ ルールベース（毎週火曜＋第2/第3月曜）の休業日Mapを当月からmonthsヶ月分生成 """
    y, m = start_date.year, start_date.month
    result = {}
    for _ in range(months):
        key = month_key(y, m)
        closed = set()

        # 1) 毎週火曜
        for d in all_days_in_month(y, m):
            if d.weekday() == 1:  # Tue
                closed.add(d)

        # 2) 第2・第3 月曜
        for nth in (2, 3):
            dm = nth_weekday_of_month(y, m, weekday=0, n=nth)  # Mon=0
            if dm:
                closed.add(dm)

        result[key] = sorted([d.strftime("%Y-%m-%d") for d in closed])

        # 次の月へ
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return result


def merge_overrides(rule_map: dict, overrides: dict):
    """
    既存の手動上書き（OVERRIDES_FILE）をマージ。
    overrides は {
        "YYYY-MM-DD": "休業日",  # 強制休業
        "YYYY-MM-DD": "営業日",  # ルールに逆らって営業
    } 形式。
    """
    if not isinstance(overrides, dict):
        overrides = {}

    # まずルールベース（毎週火曜＋第2・第3月曜）をフラットな dict に
    flat = {}
    for ym, days in rule_map.items():
        for ds in days:
            flat[ds] = True  # いったん「休業日」として登録

    # overrides を適用
    for ds, status in overrides.items():
        # 強制休業
        if status in ("休業日", "closed"):
            flat[ds] = True
        # 特別営業（ルール上は休みでも営業にする）
        elif status in ("営業日", "open"):
            flat.pop(ds, None)  # 休業フラグを削除＝営業扱い
        else:
            # その他/空値は「上書きなし」とみなす
            flat.pop(ds, None)

    # 月単位の map に戻す
    merged = {}
    for ds in sorted(flat.keys()):
        y, m, _ = ds.split("-")
        key = f"{y}-{m}"
        merged.setdefault(key, []).append(ds)
    return merged


# -----------------------------
# ページルート
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/concept")
def concept():
    return render_template("concept.html")

@app.route("/menu")
def menu():
    return render_template("menu.html")

@app.route("/color")
def color():
    return render_template("color.html")

@app.route("/straight")
def straight():
    return render_template("straight.html")

@app.route("/staff")
def staff():
    return render_template("staff.html")

@app.route("/access")
def access():
    return render_template("access.html")

@app.route("/line")
def line():
    return render_template("line.html")

@app.route("/news")
def news():
    return render_template("news.html")

@app.route("/privacy")
def privacy():
    return render_template("privacy.html")

# -----------------------------
# SEOファイル
# -----------------------------
@app.route("/sitemap.xml")
def sitemap():
    return send_from_directory(".", "sitemap.xml")

@app.route("/robots.txt")
def robots():
    return send_from_directory(".", "robots.txt")

# -----------------------------
# 管理画面・ログイン
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("password") == os.environ.get("ADMIN_PASSWORD", "cozypass"):
            session["logged_in"] = True
            return redirect(url_for("calendar_page"))
        else:
            return render_template("login.html", error="パスワードが違います")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("logged_in", None)
    return redirect(url_for("index"))

@app.route("/calendar")
def calendar_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    return render_template("calendar.html")

# -----------------------------
# お知らせ投稿
# -----------------------------
@app.route("/post", methods=["GET", "POST"])
def post_page():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        body = (request.form.get("body") or "").replace("\r\n", "\n").replace("\r", "\n")
        file = request.files.get("image")
        image_path_for_db = save_uploaded_image(file)

        if not title or not body:
            return "title/body required", 400

        p = Post(
            title=title,
            body=body,
            image=image_path_for_db,
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(p)
        db.session.commit()
        return redirect("/post")  # 重複送信防止

    posts = Post.query.order_by(Post.id.desc()).all()
    return render_template("post.html", posts=posts)

@app.route("/delete/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    if not session.get("logged_in"):
        return redirect(url_for("login"))
    p = Post.query.get_or_404(post_id)
    db.session.delete(p)
    db.session.commit()
    return redirect(url_for("post_page"))

# -----------------------------
# API（休業日 / ニュース）
# -----------------------------
@app.route("/api/holidays")
def api_holidays():
    """
    休業日マップ（当月＋翌月）を返す。
    - 自動：毎週火曜＋第2・第3月曜
    - 手動：/api/toggle で登録済みの日は「明示的な休業日」として加算
    """
    # JSTで「今日」
    today_jst = datetime.now(ZoneInfo("Asia/Tokyo")).date()

    # ルールベース生成
    base_map = generate_rule_based_closed_map(today_jst, months=2)

    # 手動上書きをマージ（存在=休業）
    overrides = load_json(OVERRIDES_FILE)  # {"YYYY-MM-DD": "休業日", ...}
    merged = merge_overrides(base_map, overrides)
    return jsonify(merged)

@app.route("/api/toggle", methods=["POST"])
def api_toggle():
    """
    管理UI用：日付の明示的な休業/営業/解除をトグル

    body の例:
      { "date": "YYYY-MM-DD", "status": "休業日" }  # 強制休業
      { "date": "YYYY-MM-DD", "status": null }      # 解除 or 特別営業化
    将来的に:
      { "date": "YYYY-MM-DD", "status": "営業日" }  # 特別営業（明示指定）も許容
    """
    if not session.get("logged_in"):
        return jsonify({"error": "login required"}), 401

    body = request.get_json(silent=True) or {}
    ds = body.get("date")
    status = body.get("status")  # "休業日" / "営業日" / None など

    if not ds:
        return jsonify({"error": "date required"}), 400

    # 文字列→date（その月のルール判定に使う）
    try:
        target_date = datetime.strptime(ds, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "invalid date format"}), 400

    overrides = load_json(OVERRIDES_FILE)
    if not isinstance(overrides, dict):
        overrides = {}

    if status is None:
        # 解除要求。ここで
        #  - ルール上 休みの日: 特別営業(営業日)にする
        #  - ルール上 営業の日: 手動設定を解除
        base_map = generate_rule_based_closed_map(target_date, months=1)
        is_rule_closed = any(
            ds in days for days in base_map.values()
        )

        if is_rule_closed:
            # もともと定休日 → 「この日だけ営業」に変更
            overrides[ds] = "営業日"
            effective_status = "営業日"
        else:
            # もともと営業日 → 手動の休業指定を解除
            overrides.pop(ds, None)
            effective_status = None

    else:
        # 明示的な指定（今のフロントは "休業日" だけ送ってくる想定）
        if status in ("休業日", "closed"):
            overrides[ds] = "休業日"
            effective_status = "休業日"
        elif status in ("営業日", "open"):
            overrides[ds] = "営業日"
            effective_status = "営業日"
        else:
            return jsonify({"error": "invalid status"}), 400

    save_json(overrides, OVERRIDES_FILE)
    return jsonify({"status": "ok", "date": ds, "effective_status": effective_status})


@app.route("/api/news", methods=["GET", "POST"])
def handle_news():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        body = (request.form.get("body") or "").replace("\r\n", "\n").replace("\r", "\n")
        file = request.files.get("image")
        image_url = save_uploaded_image(file) or ""

        if not title or not body:
            return jsonify({"error": "title/body required"}), 400

        p = Post(
            title=title,
            body=body,
            image=image_url,
            timestamp=datetime.now(timezone.utc)
        )
        db.session.add(p)
        db.session.commit()
        return jsonify({"status": "ok"})

    rows = Post.query.order_by(Post.id.desc()).all()
    data = []
    for r in rows:
        ts = r.timestamp
        if isinstance(ts, datetime):
            ts_iso = ts.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        else:
            ts_iso = str(ts)
        data.append({
            "id": r.id,
            "title": r.title,
            "body": r.body,
            "image": r.image or "",
            "timestamp": ts_iso,
        })
    return jsonify(data)

# -----------------------------
# 起動
# -----------------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
