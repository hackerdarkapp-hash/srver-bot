"""
database/db.py — طبقة قاعدة البيانات الكاملة
Buttons · Responses · Users · Settings · Tool Stats
"""

import sqlite3
import logging
import os
from typing import Optional

from config import DB_PATH

logger = logging.getLogger(__name__)

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")   # كتابة متزامنة آمنة لعدة بوتات
    c.execute("PRAGMA busy_timeout = 5000")  # انتظر 5 ث عند قفل القاعدة
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS buttons (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                parent_id   INTEGER REFERENCES buttons(id) ON DELETE CASCADE,
                label       TEXT    NOT NULL,
                section     TEXT    NOT NULL DEFAULT 'free',
                is_active   INTEGER NOT NULL DEFAULT 1,
                position    INTEGER NOT NULL DEFAULT 0,
                description TEXT,
                tool_id     TEXT,
                created_at  TEXT DEFAULT (datetime('now','localtime')),
                updated_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        # إضافة عمود tool_id إذا لم يكن موجوداً
        try:
            c.execute("ALTER TABLE buttons ADD COLUMN tool_id TEXT")
        except Exception:
            pass

        c.execute("""
            CREATE TABLE IF NOT EXISTS button_responses (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                button_id     INTEGER NOT NULL UNIQUE
                              REFERENCES buttons(id) ON DELETE CASCADE,
                response_type TEXT    NOT NULL DEFAULT 'none',
                text_content  TEXT,
                file_id       TEXT,
                file_type     TEXT,
                url           TEXT,
                caption       TEXT,
                redirect_to   INTEGER REFERENCES buttons(id),
                parse_mode    TEXT DEFAULT 'HTML'
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id    INTEGER PRIMARY KEY,
                username   TEXT,
                first_name TEXT,
                last_name  TEXT,
                phone      TEXT,
                is_blocked INTEGER DEFAULT 0,
                joined_at  TEXT DEFAULT (datetime('now','localtime')),
                last_seen  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        for col, definition in [("is_blocked", "INTEGER DEFAULT 0")]:
            try:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            except Exception:
                pass

        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS tool_usage (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id  INTEGER,
                tool_id  TEXT NOT NULL,
                used_at  TEXT DEFAULT (datetime('now','localtime'))
            )
        """)

        c.commit()
    logger.info("✅ قاعدة البيانات جاهزة")


# ══════════════════════════════════════════════════════════════
#  بذر الأدوات الافتراضية
# ══════════════════════════════════════════════════════════════

def button_exists_by_tool_id(tool_id: str) -> bool:
    with _conn() as c:
        row = c.execute("SELECT id FROM buttons WHERE tool_id=?", (tool_id,)).fetchone()
        return row is not None


def seed_default_tools(tools: list[dict]) -> None:
    """إضافة أدوات افتراضية إذا لم تكن موجودة"""
    for i, tool in enumerate(tools):
        if not button_exists_by_tool_id(tool["tool_id"]):
            with _conn() as c:
                c.execute(
                    """INSERT INTO buttons (label, section, position, tool_id)
                       VALUES (?, 'free', ?, ?)""",
                    (tool["label"], i, tool["tool_id"]),
                )
                c.commit()
            logger.info("🌱 تمت إضافة الأداة: %s", tool["label"])


# ══════════════════════════════════════════════════════════════
#  دوال الأزرار
# ══════════════════════════════════════════════════════════════

def add_button(label: str, section: str = "free", parent_id: Optional[int] = None,
               description: str = "", tool_id: Optional[str] = None) -> int:
    with _conn() as c:
        pos = c.execute(
            "SELECT COALESCE(MAX(position),0)+1 FROM buttons WHERE parent_id IS ?",
            (parent_id,)
        ).fetchone()[0]
        cur = c.execute(
            """INSERT INTO buttons (parent_id,label,section,position,description,tool_id)
               VALUES (?,?,?,?,?,?)""",
            (parent_id, label, section, pos, description, tool_id),
        )
        c.commit()
        return cur.lastrowid


def get_button(button_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM buttons WHERE id=?", (button_id,)).fetchone()
        return dict(row) if row else None


def get_children(parent_id: Optional[int]) -> list[dict]:
    with _conn() as c:
        if parent_id is None:
            rows = c.execute(
                "SELECT * FROM buttons WHERE parent_id IS NULL AND is_active=1 ORDER BY position ASC"
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM buttons WHERE parent_id=? AND is_active=1 ORDER BY position ASC",
                (parent_id,)
            ).fetchall()
        return [dict(r) for r in rows]


def get_top_level_buttons() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM buttons WHERE parent_id IS NULL ORDER BY position ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_buttons_flat() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM buttons ORDER BY parent_id NULLS FIRST, position ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def update_button(button_id: int, **kwargs) -> bool:
    allowed = {"label", "section", "is_active", "position", "description", "parent_id", "tool_id"}
    fields  = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return False
    set_clause = ", ".join(f"{k}=?" for k in fields)
    set_clause += ", updated_at=datetime('now','localtime')"
    with _conn() as c:
        cur = c.execute(
            f"UPDATE buttons SET {set_clause} WHERE id=?",
            (*fields.values(), button_id),
        )
        c.commit()
        return cur.rowcount > 0


def delete_button(button_id: int) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM buttons WHERE id=?", (button_id,))
        c.commit()
        return cur.rowcount > 0


def toggle_button(button_id: int) -> bool:
    with _conn() as c:
        row = c.execute("SELECT is_active FROM buttons WHERE id=?", (button_id,)).fetchone()
        if not row:
            return False
        new_state = 0 if row[0] else 1
        c.execute("UPDATE buttons SET is_active=? WHERE id=?", (new_state, button_id))
        c.commit()
        return bool(new_state)


def reorder_buttons(button_id: int, direction: str) -> bool:
    with _conn() as c:
        btn = c.execute("SELECT * FROM buttons WHERE id=?", (button_id,)).fetchone()
        if not btn:
            return False
        pid_clause = "parent_id IS NULL" if btn["parent_id"] is None else "parent_id=?"
        pid_args   = [] if btn["parent_id"] is None else [btn["parent_id"]]
        if direction == "up":
            sibling = c.execute(
                f"SELECT * FROM buttons WHERE {pid_clause} AND position<? ORDER BY position DESC LIMIT 1",
                (*pid_args, btn["position"]),
            ).fetchone()
        else:
            sibling = c.execute(
                f"SELECT * FROM buttons WHERE {pid_clause} AND position>? ORDER BY position ASC LIMIT 1",
                (*pid_args, btn["position"]),
            ).fetchone()
        if not sibling:
            return False
        c.execute("UPDATE buttons SET position=? WHERE id=?", (sibling["position"], button_id))
        c.execute("UPDATE buttons SET position=? WHERE id=?", (btn["position"], sibling["id"]))
        c.commit()
        return True


# ══════════════════════════════════════════════════════════════
#  دوال الردود
# ══════════════════════════════════════════════════════════════

def set_response(button_id: int, response_type: str, text_content: Optional[str] = None,
                 file_id: Optional[str] = None, file_type: Optional[str] = None,
                 url: Optional[str] = None, caption: Optional[str] = None,
                 redirect_to: Optional[int] = None, parse_mode: str = "HTML") -> None:
    with _conn() as c:
        c.execute("""
            INSERT INTO button_responses
                (button_id,response_type,text_content,file_id,file_type,url,caption,redirect_to,parse_mode)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(button_id) DO UPDATE SET
                response_type=excluded.response_type,
                text_content=excluded.text_content,
                file_id=excluded.file_id,
                file_type=excluded.file_type,
                url=excluded.url,
                caption=excluded.caption,
                redirect_to=excluded.redirect_to,
                parse_mode=excluded.parse_mode
        """, (button_id, response_type, text_content, file_id,
              file_type, url, caption, redirect_to, parse_mode))
        c.commit()


def get_response(button_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM button_responses WHERE button_id=?", (button_id,)
        ).fetchone()
        return dict(row) if row else None


def delete_response(button_id: int) -> None:
    with _conn() as c:
        c.execute("DELETE FROM button_responses WHERE button_id=?", (button_id,))
        c.commit()


# ══════════════════════════════════════════════════════════════
#  دوال المستخدمين
# ══════════════════════════════════════════════════════════════

def save_user(user_id: int, username: Optional[str], first_name: Optional[str],
              last_name: Optional[str]) -> bool:
    with _conn() as c:
        exists = c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,)).fetchone()
        if exists:
            c.execute(
                """UPDATE users SET username=?,first_name=?,last_name=?,
                   last_seen=datetime('now','localtime') WHERE user_id=?""",
                (username, first_name, last_name, user_id),
            )
            c.commit()
            return False
        c.execute(
            "INSERT INTO users(user_id,username,first_name,last_name) VALUES(?,?,?,?)",
            (user_id, username, first_name, last_name),
        )
        c.commit()
        return True


def get_user(user_id: int) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def get_all_users(page: int = 0, per_page: int = 10) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM users ORDER BY joined_at DESC LIMIT ? OFFSET ?",
            (per_page, page * per_page),
        ).fetchall()
        return [dict(r) for r in rows]


def get_users_count() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_new_users_today() -> int:
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM users WHERE date(joined_at)=date('now','localtime')"
        ).fetchone()[0]


def get_users_with_phone() -> int:
    with _conn() as c:
        return c.execute(
            "SELECT COUNT(*) FROM users WHERE phone IS NOT NULL AND phone!=''"
        ).fetchone()[0]


def save_phone(user_id: int, phone: str) -> None:
    with _conn() as c:
        c.execute("UPDATE users SET phone=? WHERE user_id=?", (phone, user_id))
        if c.execute("SELECT changes()").fetchone()[0] == 0:
            c.execute("INSERT INTO users(user_id,phone) VALUES(?,?)", (user_id, phone))
        c.commit()


def has_phone(user_id: int) -> bool:
    with _conn() as c:
        row = c.execute(
            "SELECT phone FROM users WHERE user_id=? AND phone IS NOT NULL AND phone!=''",
            (user_id,),
        ).fetchone()
        return row is not None


def toggle_block(user_id: int) -> bool:
    with _conn() as c:
        row = c.execute("SELECT is_blocked FROM users WHERE user_id=?", (user_id,)).fetchone()
        if not row:
            return False
        new = 0 if row[0] else 1
        c.execute("UPDATE users SET is_blocked=? WHERE user_id=?", (new, user_id))
        c.commit()
        return bool(new)


# ══════════════════════════════════════════════════════════════
#  دوال الإعدادات
# ══════════════════════════════════════════════════════════════

def get_setting(key: str, default: str = "") -> str:
    with _conn() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default


def set_setting(key: str, value: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        c.commit()


# ══════════════════════════════════════════════════════════════
#  إحصائيات الأدوات
# ══════════════════════════════════════════════════════════════

def log_tool_usage(user_id: int, tool_id: str) -> None:
    with _conn() as c:
        c.execute("INSERT INTO tool_usage(user_id,tool_id) VALUES(?,?)", (user_id, tool_id))
        c.commit()


def get_tool_stats() -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT tool_id, COUNT(*) as usage_count,
                   COUNT(DISTINCT user_id) as unique_users
            FROM tool_usage
            GROUP BY tool_id
            ORDER BY usage_count DESC
        """).fetchall()
        return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════
#  تحميل النسخة الاحتياطية من ملف seeds.json
# ══════════════════════════════════════════════════════════════

import json as _json

SEEDS_FILE = os.path.join(os.path.dirname(__file__), "..", "seeds.json")


def _button_exists_by_label(label: str, parent_id, section: str) -> Optional[int]:
    with _conn() as c:
        if parent_id is None:
            row = c.execute(
                "SELECT id FROM buttons WHERE label=? AND parent_id IS NULL AND section=?",
                (label, section)
            ).fetchone()
        else:
            row = c.execute(
                "SELECT id FROM buttons WHERE label=? AND parent_id=? AND section=?",
                (label, parent_id, section)
            ).fetchone()
        return row[0] if row else None


def seed_from_file() -> None:
    """يحمّل الازرار من seeds.json عند التشغيل ويتجنب التكرار."""
    path = os.path.abspath(SEEDS_FILE)
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            entries: list[dict] = _json.load(f)
    except Exception as e:
        logger.warning("seeds.json خطا في القراءة: %s", e)
        return

    id_map: dict[int, int] = {}
    for entry in entries:
        old_id  = entry["id"]
        old_pid = entry.get("parent_id")
        label   = entry["label"]
        section = entry.get("section", "free")
        new_pid = id_map.get(old_pid) if old_pid is not None else None

        existing_id = _button_exists_by_label(label, new_pid, section)
        if existing_id:
            id_map[old_id] = existing_id
            continue

        with _conn() as c:
            cur = c.execute(
                """INSERT INTO buttons (parent_id, label, section, is_active, position, description, tool_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (new_pid, label, section,
                 entry.get("is_active", 1), entry.get("position", 0),
                 entry.get("description") or "", entry.get("tool_id")),
            )
            c.commit()
            new_id = cur.lastrowid
        id_map[old_id] = new_id
        logger.info("seeds.json: تمت اضافة زر '%s' id=%d", label, new_id)

        resp = entry.get("response")
        if resp and resp.get("response_type", "none") != "none":
            try:
                set_response(
                    button_id=new_id,
                    response_type=resp.get("response_type", "none"),
                    text_content=resp.get("text_content"),
                    file_id=resp.get("file_id"),
                    file_type=resp.get("file_type"),
                    url=resp.get("url"),
                    caption=resp.get("caption"),
                    parse_mode=resp.get("parse_mode", "HTML"),
                )
            except Exception as e:
                logger.warning("خطا رد الزر '%s': %s", label, e)

    logger.info("seed_from_file: تمت معالجة %d ازرار من seeds.json", len(entries))
